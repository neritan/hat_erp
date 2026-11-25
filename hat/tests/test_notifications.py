# Copyright (c) 2026, HAT and Contributors
# See license.txt

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, now_datetime

from hat import cart, reviews
from hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing import add_to_order
from hat.hospitality_and_tourism_academy.doctype.hat_quote_request.hat_quote_request import make_quote
from hat.tests.test_cart import make_distributor, make_hotel, make_listing, make_user
from hat.tests.test_reports import make_order

PREFIX = "_Test HAT Notify"
EMAIL = PREFIX.lower().replace(" ", ".")


def inbox(user, doc=None):
	"""Subjects of the user's notifications, oldest first (about `doc` only, when given)."""
	filters = {"for_user": user}
	if doc:
		filters.update({"document_type": doc.doctype, "document_name": doc.name})
	return frappe.get_all("Notification Log", filters=filters, pluck="subject", order_by="creation asc")


class TestNotifications(IntegrationTestCase):
	"""Who hears about orders, quotes and reviews (hat/notifications.py)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.hotel = make_hotel(f"{PREFIX} Hotel")
		cls.dist = make_distributor(f"{PREFIX} Distributor")
		cls.loser = make_distributor(f"{PREFIX} Other Distributor")
		cls.listing = make_listing(cls.dist, f"{PREFIX} Wine", "Birra", 1000)
		cls.other_listing = make_listing(cls.loser, f"{PREFIX} Other Wine", "Birra", 900)
		cls.hotel_user = make_user(f"{EMAIL}.hotel@example.com", "Hotel", cls.hotel)
		cls.dist_user = make_user(f"{EMAIL}.dist@example.com", "Distributor", cls.dist)
		cls.loser_user = make_user(f"{EMAIL}.loser@example.com", "Distributor", cls.loser)

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete("HAT Distributor Rating", {"hotel": self.hotel})
		frappe.db.delete(
			"Notification Log", {"for_user": ("in", (self.hotel_user, self.dist_user, self.loser_user))}
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def place_order(self):
		frappe.set_user(self.hotel_user)
		name = add_to_order(self.listing, 2)
		cart.place_order(orders=[name])
		return frappe.get_doc("HAT Order Request", name)

	# Orders

	def test_distributor_hears_of_a_new_order_not_of_the_draft(self):
		frappe.set_user(self.hotel_user)
		name = add_to_order(self.listing, 2)
		order = frappe.get_doc("HAT Order Request", name)
		self.assertEqual(inbox(self.dist_user, order), [], "the cart is private to the hotel")

		cart.place_order(orders=[name])
		self.assertEqual(len(inbox(self.dist_user, order)), 1)
		self.assertIn("New order", inbox(self.dist_user, order)[0])
		self.assertEqual(inbox(self.hotel_user, order), [], "nobody is told of their own action")

	def test_each_status_change_reaches_the_other_side(self):
		order = self.place_order()

		frappe.set_user(self.dist_user)
		apply_workflow(frappe.get_doc("HAT Order Request", order.name), "Accept Order")
		self.assertIn("was accepted", inbox(self.hotel_user, order)[-1])

		apply_workflow(frappe.get_doc("HAT Order Request", order.name), "Mark Delivered")
		self.assertIn("delivered", inbox(self.hotel_user, order)[-1])

		frappe.set_user(self.hotel_user)
		apply_workflow(frappe.get_doc("HAT Order Request", order.name), "Confirm Receipt")
		self.assertIn("confirmed receipt", inbox(self.dist_user, order)[-1])
		self.assertEqual(len(inbox(self.dist_user, order)), 2, "new order + receipt")
		self.assertEqual(len(inbox(self.hotel_user, order)), 2, "accepted + delivered")

	def test_staff_change_reaches_both_sides(self):
		order = self.place_order()
		frappe.set_user("Administrator")
		apply_workflow(frappe.get_doc("HAT Order Request", order.name), "Decline")
		self.assertIn("was declined", inbox(self.hotel_user, order)[-1])
		self.assertIn("was declined", inbox(self.dist_user, order)[-1])

	def test_cancelling_a_draft_tells_nobody(self):
		frappe.set_user(self.hotel_user)
		order = frappe.get_doc("HAT Order Request", add_to_order(self.listing, 2))
		apply_workflow(order, "Cancel")
		self.assertEqual(inbox(self.dist_user, order), [])

	# Reviews

	def test_distributor_hears_of_reviews_and_their_changes(self):
		frappe.set_user(self.hotel_user)
		name = reviews.save_review(self.dist, rating=0.8, comment="Good")
		review = frappe.get_doc("HAT Distributor Rating", name)
		self.assertEqual(inbox(self.dist_user, review), [f"New review from {PREFIX} Hotel: 4/5"])

		reviews.save_review(self.dist, rating=0.8, comment="Good")
		self.assertEqual(len(inbox(self.dist_user, review)), 1, "an unchanged save says nothing")

		reviews.save_review(self.dist, rating=0.6, comment="Slower lately")
		self.assertEqual(inbox(self.dist_user, review)[-1], f"{PREFIX} Hotel updated its review: 3/5")

	def test_distributor_hears_of_an_order_rating(self):
		order = make_order(self.hotel, self.dist, self.listing, 1, "Completed")
		frappe.set_user(self.hotel_user)
		name = reviews.save_review(self.dist, rating=1, order_request=order.name)
		review = frappe.get_doc("HAT Distributor Rating", name)
		self.assertEqual(inbox(self.dist_user, review), [f"{PREFIX} Hotel rated order {order.name}: 5/5"])

	# Quote requests

	def test_quote_request_quote_and_award(self):
		item, group = frappe.db.get_value("HAT Listing", self.listing, ["item", "item_group"])
		frappe.set_user(self.hotel_user)
		request = frappe.get_doc(
			{
				"doctype": "HAT Quote Request",
				"title": f"{PREFIX} Wine for the bar",
				"hotel": self.hotel,
				"quote_deadline": add_days(now_datetime(), 3),
				"items": [{"item": item, "item_group": group, "description": item, "qty": 10}],
			}
		).insert()
		request.publish()
		for user in (self.dist_user, self.loser_user):
			self.assertIn("New quote request", inbox(user, request)[-1])

		quotes = {}
		for user, dist in ((self.dist_user, self.dist), (self.loser_user, self.loser)):
			frappe.set_user(user)
			quote = frappe.get_doc("HAT Quote", make_quote(request.name, dist))
			for row in quote.items:
				row.can_supply, row.rate = 1, row.rate or 950
			quote.save()
			quote.submit_quote()
			quotes[dist] = quote.name
		self.assertEqual(len(inbox(self.hotel_user, request)), 2, "one notification per quote")

		frappe.set_user(self.hotel_user)
		request.reload()
		request.award({request.items[0].name: quotes[self.dist]})
		won = frappe.get_doc("HAT Quote", quotes[self.dist])
		lost = frappe.get_doc("HAT Quote", quotes[self.loser])
		self.assertIn("awarded", inbox(self.dist_user, won)[-1])
		self.assertIn("not selected", inbox(self.loser_user, lost)[-1])
		order = frappe.get_doc("HAT Order Request", {"quote": won.name})
		self.assertIn("New order", inbox(self.dist_user, order)[-1])
