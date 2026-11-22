"""A hotel as distributors see it: read-only, with the property, location, contact and what the
distributor has done with it. Distributors open this page instead of the Customer form (see
hat.bundle.js).

Who may open it: HAT staff any hotel, a hotel its own, a distributor a hotel it deals with (an order
request, quote or partnership between them).
"""

import frappe
from frappe import _
from frappe.utils import flt

from hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing import STAFF_ROLES, get_user_hotel
from hat.hospitality_and_tourism_academy.doctype.hat_quote_request.hat_quote_request import (
	get_user_distributors,
)
from hat.hospitality_and_tourism_academy.report.utils import OPEN_STATUSES, SALE_STATUSES

RECENT = 10


@frappe.whitelist()
def get_hotel(hotel: str) -> dict:
	distributors = check_access(hotel)
	info = frappe.db.get_value(
		"Customer",
		hotel,
		[
			"name",
			"customer_name",
			"image",
			"territory",
			"email_id",
			"mobile_no",
			"website",
			"primary_address",
			"hat_star_rating",
			"hat_hotel_type",
			"hat_number_of_rooms",
			"hat_city",
			"hat_latitude",
			"hat_longitude",
		],
		as_dict=True,
	)
	return {
		"hotel": info,
		"dealings": get_dealings(hotel, distributors),
		"open_quote_requests": frappe.get_list(
			"HAT Quote Request",
			filters={"hotel": hotel, "status": "Open"},
			fields=["name", "title", "quote_deadline", "required_by"],
			order_by="quote_deadline asc",
			limit_page_length=RECENT,
		),
	}


def check_access(hotel):
	"""Return the distributors to show dealings for (None: everyone's, for staff and the hotel)."""
	if frappe.db.get_value("Customer", hotel, "customer_group") != "Hotel":
		frappe.throw(_("{0} is not a hotel").format(hotel), frappe.DoesNotExistError)
	roles = set(frappe.get_roles())
	if roles & STAFF_ROLES or ("Hotel" in roles and get_user_hotel() == hotel):
		return None
	if "Distributor" in roles:
		distributors = get_user_distributors(frappe.session.user)
		related = {"hotel": hotel, "distributor": ("in", distributors or [""])}
		if any(
			frappe.db.exists(doctype, related)
			for doctype in ("HAT Order Request", "HAT Quote", "HAT Partnership")
		):
			return distributors
	frappe.throw(_("You cannot see this hotel"), frappe.PermissionError)


def get_dealings(hotel, distributors):
	filters = {"hotel": hotel, "status": ("!=", "Draft")}
	if distributors is not None:
		filters["distributor"] = ("in", distributors or [""])
	orders = frappe.get_list(
		"HAT Order Request",
		filters=filters,
		fields=["name", "status", "transaction_date", "total_amount", "distributor_name"],
		order_by="transaction_date desc",
		limit_page_length=0,
	)
	return {
		"orders": len(orders),
		"open": sum(1 for o in orders if o.status in OPEN_STATUSES),
		"completed": sum(1 for o in orders if o.status == "Completed"),
		"ordered": sum(flt(o.total_amount) for o in orders if o.status in SALE_STATUSES),
		"last_order": orders[0].transaction_date if orders else None,
		"recent": orders[:RECENT],
	}
