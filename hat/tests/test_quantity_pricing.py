# Copyright (c) 2026, HAT and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from hat import cart
from hat.hospitality_and_tourism_academy.doctype.hat_listing import hat_listing as marketplace
from hat.hospitality_and_tourism_academy.doctype.hat_quote.hat_quote import get_quote_lines
from hat.tests.test_cart import make_distributor, make_hotel, make_user

PREFIX = "_Test HAT Qty"
TIERS = [(10, 1100), (1, 1200), (50, 950)]  # deliberately unsorted


class TestQuantityPricing(IntegrationTestCase):
	"""Price on Quantity listings (docs/specs/quantity-pricing.md)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.hotel = make_hotel(f"{PREFIX} Hotel")
		cls.partner_hotel = make_hotel(f"{PREFIX} Partner Hotel")
		cls.distributor = make_distributor(f"{PREFIX} Distributor")
		cls.listing = make_tier_listing(cls.distributor, f"{PREFIX} Towel", TIERS)
		cls.chef = make_user(f"{PREFIX.lower().replace(' ', '.')}.chef@example.com", "Hotel", cls.hotel)
		partnership = frappe.get_doc(
			{
				"doctype": "HAT Partnership",
				"distributor": cls.distributor,
				"hotel": cls.partner_hotel,
				"start_date": add_days(today(), -1),
				"discount_percentage": 10,
			}
		).insert(ignore_permissions=True)
		partnership.db_set("status", "Active")

	def setUp(self):
		super().setUp()
		frappe.db.savepoint("hat_qty_test")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="hat_qty_test")
		super().tearDown()

	def test_ranges_are_sorted_and_set_price_and_minimum(self):
		doc = frappe.get_doc("HAT Listing", self.listing)
		self.assertEqual([(r.from_qty, r.price) for r in doc.price_tiers], sorted(TIERS))
		self.assertEqual(doc.price, 1200)
		self.assertEqual(doc.minimum_qty, 1)

	def test_invalid_ranges_are_refused(self):
		for tiers in ([], [(0, 100)], [(1, 0)], [(5, 100), (5, 90)]):
			with self.subTest(tiers=tiers), self.assertRaises(frappe.ValidationError):
				make_tier_listing(self.distributor, f"{PREFIX} Bad {len(tiers)}", tiers)

	def test_whole_quantity_gets_its_range_price(self):
		doc = frappe.get_doc("HAT Listing", self.listing)
		for qty, expected in (
			(1, 1200),
			(5, 1200),
			(9.5, 1200),
			(10, 1100),
			(49, 1100),
			(50, 950),
			(60, 950),
		):
			with self.subTest(qty=qty):
				self.assertEqual(marketplace.get_listing_rate(doc, self.hotel, qty=qty), expected)

	def test_partner_discount_applies_on_top(self):
		doc = frappe.get_doc("HAT Listing", self.listing)
		self.assertEqual(marketplace.get_listing_rate(doc, self.partner_hotel, qty=10), 990)
		tiers = marketplace.get_tier_rates(doc, self.partner_hotel)
		self.assertEqual([t["rate"] for t in tiers], [1080, 990, 855])

	def test_cart_reprices_when_quantity_changes(self):
		frappe.set_user(self.chef)
		order = marketplace.add_to_order(self.listing, 5)
		line = frappe.get_doc("HAT Order Request", order).items[0]
		self.assertEqual(line.rate, 1200)
		cart.update_line(order, line.name, 60)
		doc = frappe.get_doc("HAT Order Request", order)
		self.assertEqual((doc.items[0].rate, doc.items[0].amount), (950, 57000))
		self.assertEqual(doc.request_type, "Order")

	def test_marketplace_and_quote_show_ranges(self):
		frappe.set_user(self.chef)
		offer = next(
			o
			for p in marketplace.get_marketplace(search=f"{PREFIX} Towel")["products"]
			for o in p["offers"]
			if o.name == self.listing
		)
		self.assertEqual(offer.rate, 1200)
		self.assertEqual([t["from_qty"] for t in offer.tiers], [1, 10, 50])
		frappe.set_user("Administrator")
		request = frappe.get_doc(
			{
				"doctype": "HAT Quote Request",
				"hotel": self.hotel,
				"title": f"{PREFIX} Request",
				"quote_deadline": add_days(today(), 7),
				"items": [
					{
						"item": frappe.db.get_value("HAT Listing", self.listing, "item"),
						"item_group": "Tekstile Banjoje",
						"description": f"{PREFIX} Towel",
						"qty": 20,
					}
				],
			}
		).insert(ignore_permissions=True)
		lines = get_quote_lines(request.name, self.distributor)
		self.assertEqual(lines[0]["rate"], 1100)


def make_tier_listing(distributor, product, tiers):
	item = marketplace.create_product(product, "Tekstile Banjoje", "Nos")
	return (
		frappe.get_doc(
			{
				"doctype": "HAT Listing",
				"item": item,
				"distributor": distributor,
				"price_type": "Price on Quantity",
				"price_tiers": [{"from_qty": q, "price": p} for q, p in tiers],
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


class TestMarketplaceFilters(IntegrationTestCase):
	"""Search matches products only; the distributor filter keeps that distributor's offers."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.alpha = make_distributor(f"{PREFIX} Alpha Towels")
		cls.beta = make_distributor(f"{PREFIX} Beta")
		cls.shared = make_tier_listing(cls.alpha, f"{PREFIX} Bathrobe", [(1, 2000)])
		item = frappe.db.get_value("HAT Listing", cls.shared, "item")
		frappe.get_doc(
			{"doctype": "HAT Listing", "item": item, "distributor": cls.beta, "price": 1900}
		).insert(ignore_permissions=True)
		cls.beta_only = make_tier_listing(cls.beta, f"{PREFIX} Slippers", [(1, 300)])

	def products(self, **kwargs):
		return {
			p["item_name"]: sorted(o.distributor for o in p["offers"])
			for p in marketplace.get_marketplace(page_length=500, **kwargs)["products"]
			if p["item_name"].startswith(PREFIX)
		}

	def test_search_matches_products_not_distributors(self):
		self.assertEqual(self.products(search="Alpha Towels"), {})
		self.assertEqual(list(self.products(search="Bathrobe")), [f"{PREFIX} Bathrobe"])
		code = frappe.db.get_value("HAT Listing", self.beta_only, "item")
		self.assertEqual(list(self.products(search=code)), [f"{PREFIX} Slippers"])

	def test_distributor_filter_keeps_only_its_offers(self):
		self.assertEqual(self.products(distributor=self.alpha), {f"{PREFIX} Bathrobe": [self.alpha]})
		self.assertEqual(
			self.products(distributor=self.beta),
			{f"{PREFIX} Bathrobe": [self.beta], f"{PREFIX} Slippers": [self.beta]},
		)
		self.assertEqual(self.products()[f"{PREFIX} Bathrobe"], sorted([self.alpha, self.beta]))
