import frappe


def boot_session(bootinfo):
	fix_erpnext_app_route(bootinfo)


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
