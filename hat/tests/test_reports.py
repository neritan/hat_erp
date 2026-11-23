# Copyright (c) 2026, HAT and Contributors
# See license.txt

import frappe
from frappe.desk.query_report import run
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from hat.tests.test_cart import make_distributor, make_hotel, make_listing, make_user

PREFIX = "_Test HAT Report"


class TestReports(IntegrationTestCase):
	"""The Hatix reports, and that each user only counts what they may see in the desk."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.hotel_a = make_hotel(f"{PREFIX} Hotel A")
		cls.hotel_b = make_hotel(f"{PREFIX} Hotel B")
		cls.dist_x = make_distributor(f"{PREFIX} Distributor X")
		cls.dist_y = make_distributor(f"{PREFIX} Distributor Y")
		cls.wine = make_listing(cls.dist_x, f"{PREFIX} Wine", "Birra", 1000)
		cls.water = make_listing(cls.dist_x, f"{PREFIX} Water", "Birra", 100)
		cls.juice = make_listing(cls.dist_y, f"{PREFIX} Juice", "Birra", 200)

		make_order(cls.hotel_a, cls.dist_x, cls.wine, 10, "Completed")  # 10,000
		make_order(cls.hotel_a, cls.dist_x, cls.water, 5, "Sent")  # open, not a sale
		make_order(cls.hotel_b, cls.dist_x, cls.water, 20, "Accepted")  # 2,000
		make_order(cls.hotel_b, cls.dist_y, cls.juice, 10, "Rejected")
		make_order(cls.hotel_a, cls.dist_y, cls.juice, 5, "Draft")  # a cart, never counted

		cls.hotel_user = make_user(
			f"{PREFIX.lower().replace(' ', '.')}.hotel@example.com", "Hotel", cls.hotel_a
		)
		cls.dist_user = make_user(
			f"{PREFIX.lower().replace(' ', '.')}.dist@example.com", "Distributor", cls.dist_x
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_orders_by_hotel_for_staff(self):
		rows = by_key(report("Hatix Orders by Hotel"), "hotel")
		a, b = rows[self.hotel_a], rows[self.hotel_b]
		self.assertEqual((a["requests"], a["open"], a["done"], a["ordered"]), (2, 1, 1, 10000))
		self.assertEqual((b["requests"], b["lost"], b["ordered"], b["distributors"]), (2, 1, 2000, 1))

	def test_hotel_sees_only_its_own_orders(self):
		frappe.set_user(self.hotel_user)
		rows = by_key(report("Hatix Orders by Hotel"), "hotel")
		self.assertEqual(set(rows), {self.hotel_a})

	def test_sales_by_distributor(self):
		rows = by_key(report("Hatix Sales by Distributor"), "distributor")
		x, y = rows[self.dist_x], rows[self.dist_y]
		self.assertEqual((x["requests"], x["orders"], x["hotels"], x["sales"]), (3, 2, 2, 12000))
		self.assertEqual(x["top_item"], frappe.db.get_value("HAT Listing", self.wine, "item"))
		self.assertEqual((y["requests"], y["orders"], y["lost"], y["sales"]), (1, 0, 1, 0))

	def test_distributor_sees_only_their_own_sales(self):
		frappe.set_user(self.dist_user)
		rows = by_key(report("Hatix Sales by Distributor"), "distributor")
		self.assertEqual(set(rows), {self.dist_x})

	def test_daily_activities_counts_todays_requests(self):
		frappe.set_user(self.dist_user)
		result = run("Hatix Daily Activities", filters={"from_date": today(), "to_date": today()})
		day = next(row for row in result["result"] if isinstance(row, dict))
		self.assertEqual(day["order_requests"], 3)
		self.assertEqual(day["order_value"], 10000 + 500 + 2000)

	def test_daily_activities_period_is_limited(self):
		with self.assertRaises(frappe.ValidationError):
			run("Hatix Daily Activities", filters={"from_date": add_days(today(), -400), "to_date": today()})

	def test_product_catalogue_filters(self):
		rows = report("Hatix Product Catalogue", {"distributor": self.dist_x})
		self.assertEqual({row["listing"] for row in rows}, {self.wine, self.water})
		self.assertTrue(all(not row["has_image"] for row in rows))


def make_order(hotel, distributor, listing, qty, status):
	"""An order request in `status`. Created as a draft and moved there directly: the fixture is about
	what the reports count, not the order workflow's transitions."""
	listing = frappe.db.get_value(
		"HAT Listing", listing, ["name", "item", "item_group", "price"], as_dict=True
	)
	order = frappe.get_doc(
		{
			"doctype": "HAT Order Request",
			"request_type": "Order",
			"hotel": hotel,
			"distributor": distributor,
			"transaction_date": today(),
			"items": [
				{
					"listing": listing.name,
					"item": listing.item,
					"item_group": listing.item_group,
					"description": listing.item,
					"qty": qty,
					"rate": listing.price,
				}
			],
		}
	).insert(ignore_permissions=True)
	if status != "Draft":
		frappe.db.set_value("HAT Order Request", order.name, "status", status)
	return order


def report(name, filters=None):
	filters = filters or {"from_date": add_days(today(), -7), "to_date": today()}
	return [row for row in run(name, filters=filters)["result"] if isinstance(row, dict)]


def by_key(rows, key):
	return {row[key]: row for row in rows if str(row.get(key, "")).startswith(PREFIX)}
