"""Rename the desk navigation from HAT to Hatix before the new JSON files are synced.

The Workspace, the module Sidebar, the Frappe 16 Workspace Sidebar and the Desktop Icons are
named after their label or title, so the rebrand renames them rather than relabelling them. It
runs before the model sync: otherwise the sync would add the Hatix records next to the old ones.
Rows that link to the old names (sidebar items, the desk icon's parent) follow the rename.
"""

import frappe
from frappe.model.rename_doc import rename_doc

RENAMES = (
	("Workspace", "HAT", "Hatix", ("label", "title")),
	("Workspace Sidebar", "HAT", "Hatix", ("title",)),
	("Desktop Icon", "HAT", "Hatix", ("label",)),
	# The app's own icon is named after app_title.
	("Desktop Icon", "Hospitality and Tourism Academy", "Hatix Marketplace", ("label",)),
	# Frappe 17 module sidebar: its title is the sidebar header next to the app logo.
	("Sidebar", "Hospitality and Tourism Academy", "Hatix Marketplace", ("title",)),
)


def execute():
	# Renaming in developer mode would otherwise export the records back into the app's folders.
	in_import = frappe.flags.in_import
	frappe.flags.in_import = True
	try:
		for doctype, old, new, fields in RENAMES:
			if not frappe.db.table_exists(doctype) or not frappe.db.exists(doctype, old):
				continue
			if frappe.db.exists(doctype, new):
				continue
			rename_doc(doctype, old, new, force=True, ignore_permissions=True, show_alert=False)
			frappe.db.set_value(doctype, new, {f: new for f in fields}, update_modified=False)
	finally:
		frappe.flags.in_import = in_import
