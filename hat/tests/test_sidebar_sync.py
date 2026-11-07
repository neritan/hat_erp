import json
import os
import unittest

import frappe

# The desk sidebar ships twice: Frappe 17 reads the module `Sidebar`, Frappe 16 (the deployed
# ERPNext image) reads the app-level `Workspace Sidebar`. Both must list the same entries.
V17 = (
	"hospitality_and_tourism_academy",
	"sidebar",
	"hospitality_and_tourism_academy",
	"hospitality_and_tourism_academy.json",
)
V16 = ("workspace_sidebar", "hat.json")
FIELDS = ("type", "label", "link_type", "link_to", "icon", "child", "indent", "filters")


def load(parts):
	with open(os.path.join(frappe.get_app_path("hat"), *parts)) as f:
		return json.load(f)


def entries(doc):
	return [tuple(item.get(k) or None for k in FIELDS) for item in doc["items"]]


class TestSidebarSync(unittest.TestCase):
	def test_frappe16_sidebar_matches_frappe17(self):
		v16, v17 = load(V16), load(V17)
		self.assertEqual(v16["doctype"], "Workspace Sidebar")
		self.assertEqual(v16["name"], "HAT", "Frappe 16 picks the sidebar named after the HAT workspace")
		self.assertEqual(v16["app"], "hat")
		self.assertEqual(entries(v16), entries(v17))

	def test_frappe16_header_icon_is_app_logo(self):
		# Frappe 16 draws the sidebar header from the Desktop Icon named like the sidebar; Frappe 17
		# uses the app logo. Both must show the same image.
		icon = load(("desktop_icon", "hat.json"))
		self.assertEqual(icon["name"], "HAT")
		self.assertEqual(icon["app"], "hat")
		self.assertEqual(icon["logo_url"], frappe.get_hooks("app_logo_url", app_name="hat")[0])
		self.assertTrue(
			os.path.exists(os.path.join(frappe.get_app_path("hat"), "public", "images", "hat_icon.png"))
		)
