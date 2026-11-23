# Copyright (c) 2026, HAT and Contributors
# See license.txt

import frappe
from frappe.desk.query_report import run
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from hat import cart
from hat.hospitality_and_tourism_academy.doctype.hat_listing import hat_listing as marketplace
from hat.tests.test_cart import make_distributor, make_hotel, make_listing, make_user

PREFIX = "_Test HAT Partner Privacy"
EMAIL = PREFIX.lower().replace(" ", ".")


class TestPartnershipPrivacy(IntegrationTestCase):
	"""Partnerships are between HAT and distributors: hotels get their price, never the partnership,
	the public price it discounts, or the commission behind it."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.hotel = make_hotel(f"{PREFIX} Hotel")
		cls.distributor = make_distributor(f"{PREFIX} Distributor")
		cls.listing = make_listing(cls.distributor, f"{PREFIX} Water", "Birra", 1000)
		cls.hotel_user = make_user(f"{EMAIL}.hotel@example.com", "Hotel", cls.hotel)
		partnership = frappe.get_doc(
			{
				"doctype": "HAT Partnership",
				"distributor": cls.distributor,
				"hotel": cls.hotel,
				"start_date": add_days(today(), -1),
				"discount_percentage": 10,
			}
		).insert(ignore_permissions=True)
		partnership.db_set("status", "Active")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_hotel_gets_its_price_without_the_public_one(self):
		frappe.set_user(self.hotel_user)
		price = marketplace.get_price_for_hotel(self.listing)
		self.assertEqual((price["rate"], price["public_price"]), (900, 900))
		offer = next(
			o
			for p in marketplace.get_marketplace(search=f"{PREFIX} Water")["products"]
			for o in p["offers"]
			if o.name == self.listing
		)
		self.assertEqual((offer.rate, offer.price), (900, 900))

	def test_staff_still_see_the_partner_discount(self):
		price = marketplace.get_price_for_hotel(self.listing, self.hotel)
		self.assertEqual((price["rate"], price["public_price"]), (900, 1000))

	def test_cart_does_not_flag_partnerships_to_hotels(self):
		frappe.set_user(self.hotel_user)
		order = marketplace.add_to_order(self.listing, 1)
		part = next(p for p in cart.get_cart()["parts"] if p["order"] == order)
		self.assertIsNone(part["partnership"])
		self.assertFalse(frappe.get_doc("HAT Order Request", order).has_permlevel_access_to("commission_amount"))

	def test_hotel_does_not_get_partnership_or_commission_cards(self):
		frappe.set_user(self.hotel_user)
		for card in ("Active Partnerships", "HAT Commission Earned"):
			self.assertFalse(frappe.has_permission("Number Card", doc=card), card)
		frappe.set_user("Administrator")
		self.assertTrue(frappe.has_permission("Number Card", doc="HAT Commission Earned"))

	def test_sales_report_has_no_commission_for_hotels(self):
		frappe.set_user(self.hotel_user)
		result = run("Hatix Sales by Distributor", filters={"from_date": add_days(today(), -7), "to_date": today()})
		self.assertNotIn("commission", [c.get("fieldname") for c in result["columns"]])
		self.assertNotIn("Commission", [s.get("label") for s in result.get("report_summary") or []])
