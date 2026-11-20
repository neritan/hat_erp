"""Keep the desk inside Hatix.

Hotels and distributors only work in Hatix, so they get the "Hatix" Module Profile, which hides
every other module from their desk. With Hatix as the only sidebar they can see, everything they
open (an Address from a hotel, a Contact from a distributor) stays in the Hatix sidebar, and /desk
lands on Hatix. It hides navigation only: what they may read and write is still decided by their
roles and HAT's permission rules.

Hatix staff and System Managers keep the full desk. Everyone lands on Hatix after login, because
Hatix is the site's default app.
"""

import frappe

HAT_MODULE = "Hospitality and Tourism Academy"
MODULE_PROFILE = "Hatix"
MARKETPLACE_ROLES = frozenset(("Hotel", "Distributor"))
# Roles that need the rest of the desk (ERPNext, settings) as well
FULL_DESK_ROLES = frozenset(("Administrator", "System Manager", "HAT Staff"))


def setup():
	"""after_migrate: the module profile, the users on it, and Hatix as the default app."""
	sync_module_profile()
	sync_users()
	if not frappe.db.get_single_value("System Settings", "default_app"):
		frappe.db.set_single_value("System Settings", "default_app", "hat")


def is_marketplace_only(roles) -> bool:
	roles = set(roles)
	return bool(roles & MARKETPLACE_ROLES) and not roles & FULL_DESK_ROLES


def sync_module_profile():
	"""Block every module but Hatix's own, including ones installed since the last migrate."""
	blocked = frappe.get_all(
		"Module Def", filters={"name": ["!=", HAT_MODULE]}, pluck="name", order_by="name"
	)
	if frappe.db.exists("Module Profile", MODULE_PROFILE):
		profile = frappe.get_doc("Module Profile", MODULE_PROFILE)
		if sorted(row.module for row in profile.block_modules) == blocked:
			return
	else:
		profile = frappe.new_doc("Module Profile")
		profile.module_profile_name = MODULE_PROFILE
	profile.set("block_modules", [{"module": module} for module in blocked])
	# Saving an existing profile copies its blocked modules to the users on it.
	profile.save(ignore_permissions=True)


def sync_users():
	users = frappe.get_all(
		"Has Role",
		filters={"parenttype": "User", "role": ["in", list(MARKETPLACE_ROLES)]},
		pluck="parent",
		distinct=True,
	)
	users += frappe.get_all("User", filters={"module_profile": MODULE_PROFILE}, pluck="name")
	for user in sorted(set(users)):
		doc = frappe.get_doc("User", user)
		before = doc.module_profile
		apply_module_profile(doc)
		if doc.module_profile != before:
			doc.flags.ignore_permissions = True
			doc.save()


def apply_module_profile(doc, method=None):
	"""User before_validate: put marketplace-only users on the Hatix profile, and take staff off it.

	A profile someone chose by hand is left alone. User.validate then copies the profile's blocked
	modules onto the user.
	"""
	if doc.name in ("Administrator", "Guest") or not frappe.db.exists("Module Profile", MODULE_PROFILE):
		return
	if is_marketplace_only(row.role for row in doc.roles):
		if not doc.module_profile:
			doc.module_profile = MODULE_PROFILE
	elif doc.module_profile == MODULE_PROFILE:
		doc.module_profile = None
		doc.set("block_modules", [])
