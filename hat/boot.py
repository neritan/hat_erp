import frappe

from hat.navigation import is_marketplace_only


def boot_session(bootinfo):
	keep_marketplace_users_in_hatix(bootinfo)
	fix_erpnext_app_route(bootinfo)


def keep_marketplace_users_in_hatix(bootinfo):
	"""Hotels and distributors only work in Hatix (see hat/navigation.py), so the apps screen offers
	them Hatix alone. ERPNext's app opens its Home workspace, which their module profile hides: the
	desk then looked for a Page called "home" and showed "No permission for Page"."""
	if not is_marketplace_only(frappe.get_roles()):
		return
	bootinfo["app_data"] = [app for app in bootinfo.get("app_data") or [] if app.get("app_name") == "hat"]


def fix_erpnext_app_route(bootinfo):
	"""ERPNext's app_home is /desk, which in Frappe 17 is the apps screen itself, so clicking the
	ERPNext icon there does nothing. Send it to ERPNext's Home workspace instead."""
	for app in bootinfo.get("app_data") or []:
		if (
			app.get("app_name") == "erpnext"
			and (app.get("app_route") or "").rstrip("/") == "/desk"
			and frappe.db.exists("Workspace", "Home")
		):
			app["app_route"] = "/desk/home"
