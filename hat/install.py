import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

from hat.setup.catalogue import CATALOGUE, COUNTIES

LOGO = "/assets/hat/images/hat_logo_dark.png"
ICON = "/assets/hat/images/hat_icon.png"

ROLES = ("HAT Staff", "Hotel", "Distributor")


def after_install():
	set_branding()
	setup()


def after_migrate():
	setup()


def setup():
	"""Everything HAT needs on a site. Safe to run repeatedly."""
	create_roles()
	create_party_groups()
	create_custom_fields(get_custom_fields(), update=True)
	create_item_groups()
	create_territories()
	set_role_permissions()
	create_workflows()


def create_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


def create_party_groups():
	"""Hotels are customers in the "Hotel" group; distributors are suppliers in "Distributor"."""
	for doctype, name, parent_field in (
		("Customer Group", "Hotel", "parent_customer_group"),
		("Supplier Group", "Distributor", "parent_supplier_group"),
	):
		if not frappe.db.exists(doctype, name):
			frappe.get_doc(
				{
					"doctype": doctype,
					doctype.lower().replace(" ", "_") + "_name": name,
					parent_field: f"All {doctype}s",
					"is_group": 0,
				}
			).insert(ignore_permissions=True)


def get_custom_fields():
	hotel_only = "eval:doc.customer_group=='Hotel'"
	distributor_only = "eval:doc.supplier_group=='Distributor'"
	return {
		"Customer": [
			dict(
				fieldname="hat_hotel_section",
				fieldtype="Section Break",
				label="Hotel Details",
				insert_after="language",
				depends_on=hotel_only,
				collapsible=0,
			),
			dict(
				fieldname="hat_star_rating",
				fieldtype="Select",
				label="Stars",
				options="\n1\n2\n3\n4\n5",
				insert_after="hat_hotel_section",
				in_standard_filter=1,
			),
			dict(
				fieldname="hat_hotel_type",
				fieldtype="Select",
				label="Property Type",
				options="\nHotel\nResort\nBoutique Hotel\nApartments\nRestaurant\nBar",
				insert_after="hat_star_rating",
				in_standard_filter=1,
			),
			dict(
				fieldname="hat_number_of_rooms",
				fieldtype="Int",
				label="Number of Rooms",
				insert_after="hat_hotel_type",
			),
			dict(fieldname="hat_hotel_column", fieldtype="Column Break", insert_after="hat_number_of_rooms"),
			dict(
				fieldname="hat_city",
				fieldtype="Data",
				label="City",
				insert_after="hat_hotel_column",
				in_standard_filter=1,
			),
			dict(
				fieldname="hat_latitude",
				fieldtype="Float",
				label="Latitude",
				precision="6",
				insert_after="hat_city",
			),
			dict(
				fieldname="hat_longitude",
				fieldtype="Float",
				label="Longitude",
				precision="6",
				insert_after="hat_latitude",
			),
		],
		"Supplier": [
			dict(
				fieldname="hat_distributor_section",
				fieldtype="Section Break",
				label="Distributor Details",
				insert_after="release_date",
				depends_on=distributor_only,
			),
			dict(
				fieldname="hat_categories",
				fieldtype="Table MultiSelect",
				label="Categories Supplied",
				options="HAT Category",
				insert_after="hat_distributor_section",
			),
			dict(
				fieldname="hat_coverage",
				fieldtype="Table MultiSelect",
				label="Delivery Coverage",
				options="HAT Coverage Area",
				insert_after="hat_categories",
			),
			dict(
				fieldname="hat_minimum_order",
				fieldtype="Currency",
				label="Minimum Order",
				insert_after="hat_coverage",
			),
			dict(
				fieldname="hat_distributor_column", fieldtype="Column Break", insert_after="hat_minimum_order"
			),
			dict(
				fieldname="hat_verified",
				fieldtype="Check",
				label="Verified by HAT",
				insert_after="hat_distributor_column",
				in_standard_filter=1,
				permlevel=1,
			),
			dict(
				fieldname="hat_average_rating",
				fieldtype="Rating",
				label="Average Rating from Hotels",
				insert_after="hat_verified",
				read_only=1,
				no_copy=1,
			),
			dict(
				fieldname="hat_rating_count",
				fieldtype="Int",
				label="Number of Ratings",
				insert_after="hat_average_rating",
				read_only=1,
				no_copy=1,
			),
		],
	}


def create_item_groups():
	for category, subcategories in CATALOGUE.items():
		ensure_item_group(category, "All Item Groups", is_group=1)
		for subcategory, groups in subcategories.items():
			ensure_item_group(subcategory, category, is_group=1 if groups else 0)
			for group in groups:
				ensure_item_group(group, subcategory, is_group=0)


def ensure_item_group(name, parent, is_group):
	if not frappe.db.exists("Item Group", name):
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": name,
				"parent_item_group": parent,
				"is_group": is_group,
			}
		).insert(ignore_permissions=True)


def create_territories():
	"""Albania's counties under the Albania territory, used for coverage and hotel regions."""
	if not frappe.db.exists("Territory", "Albania"):
		frappe.get_doc(
			{
				"doctype": "Territory",
				"territory_name": "Albania",
				"parent_territory": "All Territories",
				"is_group": 1,
			}
		).insert(ignore_permissions=True)
	elif not frappe.db.get_value("Territory", "Albania", "is_group"):
		frappe.db.set_value("Territory", "Albania", "is_group", 1)
	for county in COUNTIES:
		if not frappe.db.exists("Territory", county):
			frappe.get_doc(
				{
					"doctype": "Territory",
					"territory_name": county,
					"parent_territory": "Albania",
					"is_group": 0,
				}
			).insert(ignore_permissions=True)


# What hotels and distributors may do on ERPNext records. Their own Customer/Supplier is
# enforced with User Permissions, so a hotel only sees its own requests and ratings.
ERPNEXT_PERMISSIONS = {
	"Customer": {
		"Hotel": ("read", "write"),
		"Distributor": ("read",),
		"HAT Staff": ("read", "write", "create"),
	},
	"Supplier": {
		"Hotel": ("read",),
		"Distributor": ("read", "write"),
		"HAT Staff": ("read", "write", "create"),
	},
	"Item Group": {"Hotel": ("read",), "Distributor": ("read",), "HAT Staff": ("read",)},
	"Item": {"Hotel": ("read",), "Distributor": ("read",), "HAT Staff": ("read", "write", "create")},
	"Territory": {"Hotel": ("read",), "Distributor": ("read",), "HAT Staff": ("read",)},
	"Address": {
		"Hotel": ("read", "write", "create"),
		"Distributor": ("read",),
		"HAT Staff": ("read", "write", "create"),
	},
	"UOM": {"Hotel": ("read",), "Distributor": ("read",), "HAT Staff": ("read",)},
}


def set_role_permissions():
	for doctype, roles in ERPNEXT_PERMISSIONS.items():
		for role, ptypes in roles.items():
			if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
				add_permission(doctype, role, 0)
			for ptype in ptypes:
				update_permission_property(doctype, role, 0, ptype, 1, validate=False)
	# Only HAT staff can mark a distributor as verified
	if not frappe.db.exists("Custom DocPerm", {"parent": "Supplier", "role": "HAT Staff", "permlevel": 1}):
		add_permission("Supplier", "HAT Staff", 1)
	update_permission_property("Supplier", "HAT Staff", 1, "write", 1, validate=False)


WORKFLOWS = {
	"HAT Partnership": {
		"states": {
			"Draft": "HAT Staff",
			"Proposed": "HAT Staff",
			"Active": "HAT Staff",
			"Suspended": "HAT Staff",
			"Rejected": "HAT Staff",
			"Terminated": "HAT Staff",
		},
		"transitions": [
			("Draft", "Propose", "Proposed", ("HAT Staff",), None),
			("Proposed", "Approve", "Active", ("HAT Staff",), None),
			("Proposed", "Reject", "Rejected", ("HAT Staff",), None),
			("Active", "Suspend", "Suspended", ("HAT Staff",), None),
			("Suspended", "Reactivate", "Active", ("HAT Staff",), None),
			("Active", "Terminate", "Terminated", ("HAT Staff",), None),
			("Suspended", "Terminate", "Terminated", ("HAT Staff",), None),
		],
	},
	"HAT Order Request": {
		# The role that may edit the document while it sits in each state
		"states": {
			"Draft": "Hotel",
			"Sent": "Distributor",
			"Quoted": "HAT Staff",
			"Accepted": "HAT Staff",
			"Delivered": "HAT Staff",
			"Completed": "HAT Staff",
			"Rejected": "HAT Staff",
			"Cancelled": "HAT Staff",
		},
		"transitions": [
			("Draft", "Send to Distributor", "Sent", ("Hotel", "HAT Staff"), None),
			(
				"Sent",
				"Send Quote",
				"Quoted",
				("Distributor", "HAT Staff"),
				"doc.request_type == 'Request for Quotation'",
			),
			("Sent", "Accept Order", "Accepted", ("Distributor", "HAT Staff"), "doc.request_type == 'Order'"),
			("Sent", "Decline", "Rejected", ("Distributor", "HAT Staff"), None),
			("Quoted", "Accept Quote", "Accepted", ("Hotel", "HAT Staff"), None),
			("Quoted", "Reject Quote", "Rejected", ("Hotel", "HAT Staff"), None),
			("Accepted", "Mark Delivered", "Delivered", ("Distributor", "HAT Staff"), None),
			("Delivered", "Confirm Receipt", "Completed", ("Hotel", "HAT Staff"), None),
			("Draft", "Cancel", "Cancelled", ("Hotel", "HAT Staff"), None),
			("Sent", "Cancel", "Cancelled", ("Hotel", "HAT Staff"), None),
			("Quoted", "Cancel", "Cancelled", ("Hotel", "HAT Staff"), None),
		],
	},
}


def create_workflows():
	for doctype, spec in WORKFLOWS.items():
		for state in spec["states"]:
			if not frappe.db.exists("Workflow State", state):
				frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state}).insert(
					ignore_permissions=True
				)
		for _state, action, _next, _roles, _cond in spec["transitions"]:
			if not frappe.db.exists("Workflow Action Master", action):
				frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
					ignore_permissions=True
				)

		name = doctype
		workflow = (
			frappe.get_doc("Workflow", name)
			if frappe.db.exists("Workflow", name)
			else frappe.new_doc("Workflow")
		)
		workflow.update(
			{
				"workflow_name": name,
				"document_type": doctype,
				"workflow_state_field": "status",
				"is_active": 1,
				"send_email_alert": 0,
			}
		)
		workflow.set(
			"states",
			[
				{"state": state, "doc_status": "0", "allow_edit": role}
				for state, role in spec["states"].items()
			],
		)
		workflow.set(
			"transitions",
			[
				{
					"state": state,
					"action": action,
					"next_state": next_state,
					"allowed": role,
					"allow_self_approval": 1,
					"condition": condition,
				}
				for state, action, next_state, roles, condition in spec["transitions"]
				for role in roles
			],
		)
		workflow.save(ignore_permissions=True)


def set_branding():
	"""Brand the site with the HAT logo, leaving any value already set alone."""
	set_if_empty(
		"Website Settings",
		{
			"app_name": "Hospitality and Tourism Academy",
			"app_logo": LOGO,
			"favicon": ICON,
			"splash_image": ICON,
		},
	)
	set_if_empty("Navbar Settings", {"app_logo": LOGO})


def set_if_empty(doctype, values):
	doc = frappe.get_single(doctype)
	changed = False
	for field, value in values.items():
		# "Frappe" is the framework's default app_name, not a user's choice
		if doc.get(field) in (None, "", "Frappe"):
			doc.set(field, value)
			changed = True
	if changed:
		doc.flags.ignore_mandatory = True
		doc.save(ignore_permissions=True)
