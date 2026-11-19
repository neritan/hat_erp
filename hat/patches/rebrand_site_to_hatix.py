"""Swap the HAT name and logos for Hatix on sites installed before the rebrand.

Only values that are still HAT's defaults are replaced, so a logo or name a site chose itself
stays. The old image files are gone from the app, so leaving them would show broken images.
"""

import frappe

from hat.install import APP_NAME, FAVICON, LOGO, SPLASH

OLD_ICON = "/assets/hat/images/hat_icon.png"
OLD_LOGOS = ("/assets/hat/images/hat_logo_dark.png", "/assets/hat/images/hat_logo.png", OLD_ICON)

SETTINGS = {
	"Website Settings": {
		"app_name": (("Hospitality and Tourism Academy",), APP_NAME),
		"app_logo": (OLD_LOGOS, LOGO),
		"favicon": ((OLD_ICON,), FAVICON),
		"splash_image": ((OLD_ICON,), SPLASH),
	},
	"Navbar Settings": {"app_logo": (OLD_LOGOS, LOGO)},
}


def execute():
	for doctype, fields in SETTINGS.items():
		for field, (old_values, new) in fields.items():
			if frappe.db.get_single_value(doctype, field) in old_values:
				frappe.db.set_single_value(doctype, field, new)

	for name, logo_url in frappe.get_all("Desktop Icon", {"app": "hat"}, ["name", "logo_url"], as_list=True):
		if logo_url in OLD_LOGOS:
			frappe.db.set_value("Desktop Icon", name, "logo_url", "/assets/hat/images/hatix-app-icon-512.png")

	frappe.clear_cache()
