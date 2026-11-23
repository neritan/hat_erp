# Copyright (c) 2026, HAT and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hat.tests.test_cart import make_distributor, make_hotel

PREFIX = "_Test HAT Structure"
EMAIL = PREFIX.lower().replace(" ", ".")


def new_user(email, roles, **fields):
	return frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": email.split("@")[0],
			"send_welcome_email": 0,
			"roles": [{"role": role} for role in roles],
			**fields,
		}
	)


def party_permissions(user):
	return sorted(
		(p.allow, p.for_value)
		for p in frappe.get_all(
			"User Permission",
			filters={"user": user, "allow": ("in", ("Customer", "Supplier"))},
			fields=["allow", "for_value"],
		)
	)


class TestUserStructure(IntegrationTestCase):
	"""A hotel or distributor user belongs to exactly one hotel or distributor (hat/users.py)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.hotel = make_hotel(f"{PREFIX} Hotel")
		cls.other_hotel = make_hotel(f"{PREFIX} Other Hotel")
		cls.dist = make_distributor(f"{PREFIX} Distributor")

	def setUp(self):
		# Each test creates its users from scratch
		for user in frappe.get_all("User", filters={"name": ("like", f"{EMAIL}.%")}, pluck="name"):
			frappe.db.delete("User Permission", {"user": user})
			frappe.delete_doc("User", user, force=True, ignore_permissions=True)

	def test_hotel_user_needs_a_hotel(self):
		user = new_user(f"{EMAIL}.nohotel@example.com", ["Hotel"])
		self.assertRaises(frappe.ValidationError, user.insert, ignore_permissions=True)

	def test_distributor_user_needs_a_distributor(self):
		user = new_user(f"{EMAIL}.nodist@example.com", ["Distributor"])
		self.assertRaises(frappe.ValidationError, user.insert, ignore_permissions=True)

	def test_hotel_and_distributor_roles_together_are_refused(self):
		user = new_user(
			f"{EMAIL}.both@example.com",
			["Hotel", "Distributor"],
			hat_hotel=self.hotel,
			hat_distributor=self.dist,
		)
		self.assertRaises(frappe.ValidationError, user.insert, ignore_permissions=True)

	def test_structure_must_be_of_the_right_group(self):
		user = new_user(f"{EMAIL}.wrong@example.com", ["Distributor"], hat_distributor=self.hotel)
		self.assertRaises(frappe.ValidationError, user.insert, ignore_permissions=True)

	def test_user_permission_follows_the_structure(self):
		user = new_user(f"{EMAIL}.hotel@example.com", ["Hotel"], hat_hotel=self.hotel)
		user.insert(ignore_permissions=True)
		self.assertEqual(party_permissions(user.name), [("Customer", self.hotel)])

		# A permission added by hand to another hotel goes on the next save
		frappe.get_doc(
			{"doctype": "User Permission", "user": user.name, "allow": "Customer", "for_value": self.other_hotel}
		).insert(ignore_permissions=True)
		user.reload()
		user.hat_hotel = self.other_hotel
		user.save(ignore_permissions=True)
		self.assertEqual(party_permissions(user.name), [("Customer", self.other_hotel)])

	def test_distributor_gets_its_supplier_permission(self):
		user = new_user(f"{EMAIL}.dist@example.com", ["Distributor"], hat_distributor=self.dist)
		user.insert(ignore_permissions=True)
		self.assertEqual(party_permissions(user.name), [("Supplier", self.dist)])
		self.assertIsNone(user.hat_hotel)

	def test_staff_need_no_structure(self):
		user = new_user(f"{EMAIL}.staff@example.com", ["Hotel", "Distributor", "HAT Staff"])
		user.insert(ignore_permissions=True)
		self.assertEqual(party_permissions(user.name), [])
