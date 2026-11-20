# Copyright (c) 2026, HAT and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from hat import cart
from hat.hospitality_and_tourism_academy.doctype.hat_listing import hat_listing as marketplace

PREFIX = "_Test HAT Cart"


class TestCart(IntegrationTestCase):
	"""The hotel cart (hat/cart.py) and the hotel access rule it relies on (resolve_hotel).

	Fixtures are created here and rolled back with the class; each test runs under its own
	savepoint, so every test starts with empty carts."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.hotel_a = make_hotel(f"{PREFIX} Hotel A")
		cls.hotel_b = make_hotel(f"{PREFIX} Hotel B")
		cls.with_minimum = make_distributor(f"{PREFIX} Distributor Minimum", minimum_order=15000)
		cls.no_minimum = make_distributor(f"{PREFIX} Distributor Free")
		cls.beer = make_listing(cls.with_minimum, f"{PREFIX} Beer crate", "Birra", 1000, minimum_qty=2)
		cls.coffee = make_listing(cls.no_minimum, f"{PREFIX} Coffee 1 kg", "Kafe", 500)
		cls.tea = make_listing(cls.no_minimum, f"{PREFIX} Tea box", "Kafe", 300)
		cls.chef = make_user(f"{PREFIX.lower().replace(' ', '.')}.chef@example.com", "Hotel", cls.hotel_a)
		cls.manager = make_user(
			f"{PREFIX.lower().replace(' ', '.')}.manager@example.com", "Hotel", cls.hotel_a
		)
		cls.other = make_user(f"{PREFIX.lower().replace(' ', '.')}.other@example.com", "Hotel", cls.hotel_b)
		cls.staff = make_user(f"{PREFIX.lower().replace(' ', '.')}.staff@example.com", "HAT Staff")

	def setUp(self):
		super().setUp()
		frappe.db.savepoint("hat_cart_test")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="hat_cart_test")
		super().tearDown()

	def part(self, cart_data, distributor):
		return next(p for p in cart_data["parts"] if p["distributor"] == distributor)

	def test_cart_is_shared_by_the_hotels_users(self):
		frappe.set_user(self.chef)
		marketplace.add_to_order(self.beer, 2)
		frappe.set_user(self.manager)
		data = cart.get_cart()
		self.assertEqual(data["hotel"], self.hotel_a)
		self.assertEqual(data["count"], 1)
		frappe.set_user(self.other)
		self.assertEqual(cart.get_cart()["parts"], [])
		self.assertEqual(cart.get_cart_count(), 0)

	def test_another_hotel_cannot_be_used(self):
		frappe.set_user(self.chef)
		marketplace.add_to_order(self.beer, 2)
		frappe.set_user(self.other)
		calls = {
			"get_cart": lambda: cart.get_cart(self.hotel_a),
			"get_cart_count": lambda: cart.get_cart_count(self.hotel_a),
			"place_order": lambda: cart.place_order(hotel=self.hotel_a),
			"add_to_order": lambda: marketplace.add_to_order(self.beer, 2, self.hotel_a),
			"get_price_for_hotel": lambda: marketplace.get_price_for_hotel(self.beer, self.hotel_a),
			"get_marketplace": lambda: marketplace.get_marketplace(hotel=self.hotel_a),
		}
		for name, call in calls.items():
			with self.subTest(name), self.assertRaises(frappe.PermissionError):
				call()
		frappe.set_user(self.staff)
		self.assertEqual(cart.get_cart(self.hotel_a)["count"], 1)

	def test_totals_and_count_are_consistent(self):
		frappe.set_user(self.chef)
		marketplace.add_to_order(self.beer, 3)
		marketplace.add_to_order(self.coffee, 4)
		marketplace.add_to_order(self.tea, 5)
		data = cart.get_cart()
		lines = [line for p in data["parts"] for line in p["lines"]]
		self.assertEqual(len(data["parts"]), 2)
		self.assertEqual(data["count"], len(lines))
		self.assertEqual(cart.get_cart_count(), len(lines))
		for p in data["parts"]:
			self.assertEqual(p["total"], sum(line["amount"] for line in p["lines"]))
		self.assertEqual(data["total"], sum(p["total"] for p in data["parts"]))
		self.assertEqual(data["total"], 3 * 1000 + 4 * 500 + 5 * 300)

	def test_quantity_change_and_removal(self):
		frappe.set_user(self.chef)
		marketplace.add_to_order(self.coffee, 4)
		p = self.part(cart.get_cart(), self.no_minimum)
		cart.update_line(p["order"], p["lines"][0]["name"], 10)
		self.assertEqual(self.part(cart.get_cart(), self.no_minimum)["total"], 5000)
		cart.remove_line(p["order"], p["lines"][0]["name"])
		self.assertFalse(frappe.db.exists("HAT Order Request", p["order"]))
		self.assertEqual(cart.get_cart()["parts"], [])

	def test_listing_minimum_quantity_is_enforced(self):
		frappe.set_user(self.chef)
		marketplace.add_to_order(self.beer, 2)
		p = self.part(cart.get_cart(), self.with_minimum)
		with self.assertRaises(frappe.ValidationError):
			cart.update_line(p["order"], p["lines"][0]["name"], 1)

	def test_minimum_order_warns_but_still_sends(self):
		frappe.set_user(self.chef)
		marketplace.add_to_order(self.beer, 2)  # 2,000 of a 15,000 minimum
		p = self.part(cart.get_cart(), self.with_minimum)
		self.assertEqual(p["missing"], 13000)
		result = cart.place_order(required_by=add_days(today(), 2), notes="Back entrance")
		self.assertEqual([s["order"] for s in result["sent"]], [p["order"]])
		self.assertEqual(len(result["warnings"]), 1)
		order = frappe.get_doc("HAT Order Request", p["order"])
		self.assertEqual(order.status, "Sent")
		self.assertEqual(str(order.required_by), add_days(today(), 2))
		self.assertIn("Back entrance", order.notes)

	def test_one_failing_order_does_not_block_the_others(self):
		for error in (frappe.ValidationError("Listing changed"), frappe.PermissionError("No write access")):
			with self.subTest(error=type(error).__name__):
				frappe.db.savepoint("hat_cart_subtest")
				frappe.set_user(self.chef)
				marketplace.add_to_order(self.beer, 2)
				marketplace.add_to_order(self.coffee, 2)
				failing = self.part(cart.get_cart(), self.with_minimum)["order"]
				with patch("hat.cart.get_cart_order", side_effect=fail_for(failing, error)):
					result = cart.place_order()
				self.assertEqual([f["order"] for f in result["failed"]], [failing])
				self.assertEqual(len(result["sent"]), 1)
				self.assertEqual(frappe.db.get_value("HAT Order Request", failing, "status"), "Draft")
				frappe.set_user("Administrator")
				frappe.db.rollback(save_point="hat_cart_subtest")

	def test_unexpected_error_is_logged_and_reported_generically(self):
		frappe.set_user(self.chef)
		marketplace.add_to_order(self.beer, 2)
		marketplace.add_to_order(self.coffee, 2)
		failing = self.part(cart.get_cart(), self.no_minimum)["order"]
		with (
			patch("hat.cart.get_cart_order", side_effect=fail_for(failing, RuntimeError("boom"))),
			patch("frappe.log_error") as log_error,
		):
			result = cart.place_order()
		log_error.assert_called_once()
		self.assertEqual(len(result["sent"]), 1)
		self.assertNotIn("boom", result["failed"][0]["error"])

	def test_database_failure_aborts_the_whole_request(self):
		frappe.set_user(self.chef)
		marketplace.add_to_order(self.beer, 2)
		marketplace.add_to_order(self.coffee, 2)
		failing = self.part(cart.get_cart(), self.no_minimum)["order"]
		with (
			patch(
				"hat.cart.get_cart_order",
				side_effect=fail_for(failing, frappe.QueryDeadlockError("deadlock")),
			),
			self.assertRaises(frappe.QueryDeadlockError),
		):
			cart.place_order()

	def test_place_only_one_distributor(self):
		frappe.set_user(self.chef)
		marketplace.add_to_order(self.beer, 2)
		marketplace.add_to_order(self.coffee, 2)
		only = self.part(cart.get_cart(), self.no_minimum)["order"]
		result = cart.place_order(orders=[only])
		self.assertEqual([s["order"] for s in result["sent"]], [only])
		self.assertEqual([p["distributor"] for p in cart.get_cart()["parts"]], [self.with_minimum])

	def test_empty_cart_cannot_be_placed(self):
		frappe.set_user(self.chef)
		with self.assertRaises(frappe.ValidationError):
			cart.place_order()

	def test_lines_from_unavailable_listings_are_flagged(self):
		frappe.set_user(self.chef)
		marketplace.add_to_order(self.beer, 2)
		marketplace.add_to_order(self.coffee, 2)
		marketplace.add_to_order(self.tea, 2)
		frappe.set_user("Administrator")
		frappe.delete_doc("HAT Listing", self.beer, force=True, ignore_permissions=True)
		frappe.db.set_value("HAT Listing", self.coffee, "availability", "Out of Stock")
		frappe.set_user(self.chef)
		flags = {
			line["listing"]: line["unavailable"] for p in cart.get_cart()["parts"] for line in p["lines"]
		}
		self.assertEqual(flags, {self.beer: True, self.coffee: True, self.tea: False})

	def test_get_cart_query_count_does_not_grow_with_the_cart(self):
		frappe.set_user(self.chef)
		marketplace.add_to_order(self.coffee, 2)
		cart.get_cart()  # warm the metadata cache
		small = count_queries(cart.get_cart)
		marketplace.add_to_order(self.beer, 2)
		marketplace.add_to_order(self.tea, 2)
		self.assertEqual(count_queries(cart.get_cart), small)


def fail_for(order, error):
	"""get_cart_order that raises `error` for one order and works for the rest."""

	def get_cart_order(name):
		if name == order:
			raise error
		return original_get_cart_order(name)

	return get_cart_order


original_get_cart_order = cart.get_cart_order


def count_queries(fn):
	real, calls = frappe.db.sql, []

	def counting(*args, **kwargs):
		calls.append(args[0] if args else None)
		return real(*args, **kwargs)

	frappe.db.sql = counting
	try:
		fn()
	finally:
		frappe.db.sql = real
	return len(calls)


def make_hotel(name):
	if not frappe.db.exists("Customer", name):
		frappe.get_doc(
			{"doctype": "Customer", "customer_name": name, "customer_group": "Hotel", "territory": "Tiranë"}
		).insert(ignore_permissions=True)
	return name


def make_distributor(name, minimum_order=0):
	if not frappe.db.exists("Supplier", name):
		frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": name,
				"supplier_group": "Distributor",
				"hat_verified": 1,
				"hat_minimum_order": minimum_order,
			}
		).insert(ignore_permissions=True)
	return name


def make_listing(distributor, product, item_group, price, minimum_qty=1):
	item = marketplace.create_product(product, item_group, "Nos")
	return (
		frappe.get_doc(
			{
				"doctype": "HAT Listing",
				"item": item,
				"distributor": distributor,
				"price": price,
				"minimum_qty": minimum_qty,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def make_user(email, role, hotel=None):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"roles": [{"role": role}],
			}
		).insert(ignore_permissions=True)
	if hotel:
		frappe.get_doc(
			{"doctype": "User Permission", "user": email, "allow": "Customer", "for_value": hotel}
		).insert(ignore_permissions=True)
	return email
