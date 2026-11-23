# Copyright (c) 2026, HAT and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hat import cart, reviews
from hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing import add_to_order
from hat.hospitality_and_tourism_academy.page.hat_distributor.hat_distributor import get_distributor
from hat.hospitality_and_tourism_academy.page.hat_hotel.hat_hotel import get_hotel
from hat.tests.test_cart import make_distributor, make_hotel, make_listing, make_user
from hat.tests.test_reports import make_order

PREFIX = "_Test HAT Views"


class TestHotelViews(IntegrationTestCase):
	"""What hotels and distributors see of each other: partnerships, reviews, the read-only pages."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.hotel = make_hotel(f"{PREFIX} Hotel")
		cls.other_hotel = make_hotel(f"{PREFIX} Other Hotel")
		cls.dist = make_distributor(f"{PREFIX} Distributor")
		cls.stranger = make_distributor(f"{PREFIX} Unverified")
		frappe.db.set_value("Supplier", cls.stranger, "hat_verified", 0)
		listing = cls.listing = make_listing(cls.dist, f"{PREFIX} Coffee", "Birra", 500)
		cls.completed = make_order(cls.hotel, cls.dist, listing, 2, "Completed").name
		cls.sent = make_order(cls.hotel, cls.dist, listing, 2, "Sent").name

		email = PREFIX.lower().replace(" ", ".")
		cls.hotel_user = make_user(f"{email}.hotel@example.com", "Hotel", cls.hotel)
		cls.dist_user = make_user(f"{email}.dist@example.com", "Distributor", cls.dist)

	def setUp(self):
		# Each test starts without ratings (the class fixtures are shared)
		frappe.db.delete("HAT Distributor Rating", {"hotel": ("like", f"{PREFIX}%")})

	def tearDown(self):
		frappe.set_user("Administrator")

	# Partnerships

	def test_hotel_cannot_read_partnerships(self):
		frappe.set_user(self.hotel_user)
		self.assertFalse(frappe.has_permission("HAT Partnership", "read"))
		self.assertRaises(frappe.PermissionError, frappe.get_list, "HAT Partnership")
		order = frappe.get_doc("HAT Order Request", self.completed)
		self.assertFalse(order.has_permlevel_access_to("partnership"))

	def test_cart_still_works_for_hotels(self):
		frappe.set_user(self.hotel_user)
		self.assertIn("parts", cart.get_cart())

	def test_distributor_still_reads_partnerships(self):
		frappe.set_user(self.dist_user)
		self.assertTrue(frappe.has_permission("HAT Partnership", "read"))

	# Reviews

	def test_hotel_reviews_distributor_once_overall(self):
		frappe.set_user(self.hotel_user)
		first = reviews.save_review(self.dist, rating=0.8, comment="Good")
		second = reviews.save_review(self.dist, rating=0.6, comment="Okay")
		self.assertEqual(first, second, "saving again edits the overall review")
		review = frappe.get_doc("HAT Distributor Rating", first)
		self.assertEqual((review.review_type, review.rating, review.comment), ("Overall", 0.6, "Okay"))

		duplicate = frappe.get_doc(
			{
				"doctype": "HAT Distributor Rating",
				"hotel": self.hotel,
				"distributor": self.dist,
				"rating": 0.4,
			}
		)
		self.assertRaises(frappe.ValidationError, duplicate.insert)

	def test_hotel_rates_each_completed_order(self):
		frappe.set_user(self.hotel_user)
		name = reviews.save_review(self.dist, rating=1, order_request=self.completed)
		self.assertEqual(frappe.db.get_value("HAT Distributor Rating", name, "review_type"), "Order")
		self.assertRaises(
			frappe.ValidationError, reviews.save_review, self.dist, rating=1, order_request=self.sent
		)

	def test_order_rating_is_about_the_orders_distributor(self):
		frappe.set_user(self.hotel_user)
		name = reviews.save_review(self.stranger, rating=1, order_request=self.completed)
		self.assertEqual(frappe.db.get_value("HAT Distributor Rating", name, "distributor"), self.dist)

	def test_distributor_cannot_rate_itself(self):
		frappe.set_user(self.dist_user)
		self.assertFalse(frappe.has_permission("HAT Distributor Rating", "create"))
		self.assertRaises(frappe.PermissionError, reviews.save_review, self.dist, rating=1)

	# Orders: hotels place them, distributors fulfil them

	def test_distributor_cannot_order(self):
		frappe.set_user(self.dist_user)
		self.assertFalse(frappe.has_permission("HAT Order Request", "create"))
		self.assertFalse(frappe.has_permission("HAT Order Request", "delete", self.sent))
		self.assertRaises(frappe.PermissionError, add_to_order, self.listing, 1, self.hotel)

	def test_distributor_still_fulfils_orders(self):
		frappe.set_user(self.dist_user)
		self.assertTrue(frappe.has_permission("HAT Order Request", "write", self.sent))

	# Distributor page (hotels)

	def test_hotel_sees_distributor_page(self):
		frappe.set_user(self.hotel_user)
		reviews.save_review(self.dist, rating=0.8, comment="Fast delivery")
		data = get_distributor(self.dist)
		self.assertEqual(data["distributor"].supplier_name, self.dist)
		self.assertTrue(data["can_review"])
		self.assertEqual(data["with_hotel"]["to_rate"], [self.completed])
		self.assertEqual(data["with_hotel"]["review"].rating, 0.8)
		self.assertEqual([r.comment for r in data["reviews"]], ["Fast delivery"])
		self.assertEqual(data["products"]["total"], 1)

	def test_hotel_cannot_see_unverified_stranger(self):
		frappe.set_user(self.hotel_user)
		self.assertRaises(frappe.PermissionError, get_distributor, self.stranger)

	# Hotel page (distributors)

	def test_distributor_sees_hotel_it_deals_with(self):
		frappe.set_user(self.dist_user)
		data = get_hotel(self.hotel)
		self.assertEqual(data["dealings"]["orders"], 2)
		self.assertEqual(data["dealings"]["completed"], 1)

	def test_distributor_sees_any_hotel_but_only_its_dealings(self):
		frappe.set_user(self.dist_user)
		data = get_hotel(self.other_hotel)
		self.assertEqual(data["hotel"].name, self.other_hotel)
		self.assertEqual(data["dealings"]["orders"], 0)

	def test_distributor_sees_only_its_own_distributor_page(self):
		frappe.set_user(self.dist_user)
		self.assertEqual(get_distributor(self.dist)["distributor"].supplier_name, self.dist)
		self.assertRaises(frappe.PermissionError, get_distributor, self.stranger)

	def test_hotel_sees_only_its_own_page(self):
		frappe.set_user(self.hotel_user)
		self.assertEqual(get_hotel(self.hotel)["hotel"].name, self.hotel)
		self.assertRaises(frappe.PermissionError, get_hotel, self.other_hotel)


class TestVerifiedDistributorSearch(IntegrationTestCase):
	def test_hotel_can_search_verified_distributors(self):
		from frappe.desk.search import search_link

		frappe.set_user("Administrator")
		verified = make_distributor(f"{PREFIX} Search Verified")
		hidden = make_distributor(f"{PREFIX} Search Unverified")
		frappe.db.set_value("Supplier", hidden, "hat_verified", 0)
		hotel_user = make_user(
			f"{PREFIX.lower().replace(' ', '.')}.search@example.com", "Hotel", make_hotel(f"{PREFIX} Hotel")
		)
		frappe.set_user(hotel_user)
		try:
			found = search_link(
				"Supplier",
				f"{PREFIX} Search",
				query="hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing.verified_distributor_query",
			)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual([row["value"] for row in found], [verified])
