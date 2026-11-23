"""One structure per marketplace user.

A hotel user works for exactly one hotel (a Customer in the "Hotel" group) and a distributor user
for exactly one distributor (a Supplier in the "Distributor" group). The structure is chosen on the
User form (`hat_hotel` / `hat_distributor`) when the user gets the Hotel or Distributor role, and
HAT keeps the user's User Permission in step with it: that permission is what limits the user to
their own hotel's or distributor's records.

HAT staff and System Managers are left alone: they work across every hotel and distributor, and a
User Permission would shut them out of all the others.
"""

import frappe
from frappe import _

from hat.navigation import is_marketplace_only

# role: (User field, linked doctype, group field, group)
STRUCTURES = {
	"Hotel": ("hat_hotel", "Customer", "customer_group", "Hotel"),
	"Distributor": ("hat_distributor", "Supplier", "supplier_group", "Distributor"),
}
PARTY_DOCTYPES = ("Customer", "Supplier")


def get_structure_role(roles):
	"""The Hotel or Distributor role of a marketplace-only user, or None for everyone else."""
	roles = set(roles)
	if not is_marketplace_only(roles):
		return None
	return next(role for role in STRUCTURES if role in roles)


def validate(doc, method=None):
	"""User validate: a marketplace user has one role, Hotel or Distributor, and its structure."""
	roles = {row.role for row in doc.roles}
	if not is_marketplace_only(roles):
		return
	if all(role in roles for role in STRUCTURES):
		frappe.throw(
			_("{0} can belong to one hotel or one distributor, not both. Keep only the Hotel or the Distributor role.").format(
				frappe.bold(doc.name)
			),
			title=_("One structure per user"),
		)
	role = get_structure_role(roles)
	field, doctype, group_field, group = STRUCTURES[role]
	for other, (other_field, *_rest) in STRUCTURES.items():
		if other != role:
			doc.set(other_field, None)

	value = doc.get(field)
	if not value:
		frappe.throw(
			_("Choose the {0} that {1} belongs to.").format(_(role).lower(), frappe.bold(doc.name)),
			title=_("Missing {0}").format(_(role)),
		)
	if frappe.db.get_value(doctype, value, group_field) != group:
		frappe.throw(_("{0} is not a {1}").format(frappe.bold(value), _(role).lower()))


def sync_permission(doc, method=None):
	"""User on_update: the user's only Customer / Supplier permission is their structure."""
	role = get_structure_role(row.role for row in doc.roles)
	if not role:
		return
	field, doctype, *_rest = STRUCTURES[role]
	value = doc.get(field)
	if not value:
		return

	kept = False
	for perm in frappe.get_all(
		"User Permission",
		filters={"user": doc.name, "allow": ("in", PARTY_DOCTYPES)},
		fields=["name", "allow", "for_value"],
	):
		if not kept and perm.allow == doctype and perm.for_value == value:
			kept = True
		else:
			frappe.delete_doc("User Permission", perm.name, ignore_permissions=True)
	if not kept:
		frappe.get_doc(
			{"doctype": "User Permission", "user": doc.name, "allow": doctype, "for_value": value}
		).insert(ignore_permissions=True)


def backfill():
	"""after_migrate: fill an empty structure from the user's one matching User Permission.

	Users set up before the structure fields existed were linked by hand. Users with none, or with
	several, stay empty, and the User form asks for the structure the next time they are saved.
	"""
	for role, (field, doctype, group_field, group) in STRUCTURES.items():
		users = frappe.get_all(
			"Has Role", filters={"parenttype": "User", "role": role}, pluck="parent", distinct=True
		)
		for user in users:
			if frappe.db.get_value("User", user, field):
				continue
			if get_structure_role(frappe.get_roles(user)) != role:
				continue
			linked = [
				name
				for name in frappe.get_all(
					"User Permission", filters={"user": user, "allow": doctype}, pluck="for_value"
				)
				if frappe.db.get_value(doctype, name, group_field) == group
			]
			if len(linked) == 1:
				frappe.db.set_value("User", user, field, linked[0], update_modified=False)
