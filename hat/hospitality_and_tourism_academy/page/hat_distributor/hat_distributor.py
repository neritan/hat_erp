"""A distributor as hotels see it: read-only, with contact, coverage, categories, ratings and reviews,
and its products. Hotels open this page instead of the Supplier form (see hat.bundle.js).

Who may open it: HAT staff any distributor, a distributor their own, a hotel any verified
distributor (the ones the marketplace shows) or one it has dealt with.
"""

import frappe
from frappe import _
from frappe.utils import flt

from hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing import (
	STAFF_ROLES,
	get_distributor_cards,
	resolve_hotel,
)
from hat.hospitality_and_tourism_academy.doctype.hat_quote_request.hat_quote_request import (
	get_user_distributors,
)
from hat.hospitality_and_tourism_academy.report.utils import SALE_STATUSES

REVIEWS = 30
PRODUCTS = 12


@frappe.whitelist()
def get_distributor(distributor: str, hotel: str | None = None) -> dict:
	hotel = resolve_hotel(hotel) if "Hotel" in frappe.get_roles() or hotel else None
	check_access(distributor, hotel)

	card = get_distributor_cards([distributor], hotel)[0]
	card.update(
		frappe.db.get_value(
			"Supplier",
			distributor,
			["image", "hat_rating_count", "supplier_details", "country"],
			as_dict=True,
		)
	)
	card.categories = frappe.get_all(
		"HAT Category",
		filters={"parenttype": "Supplier", "parent": distributor},
		pluck="item_group",
		order_by="idx asc",
	)
	return {
		"distributor": card,
		"scores": get_scores(distributor),
		"reviews": get_reviews(distributor),
		"products": get_products(distributor),
		"hotel": hotel,
		"with_hotel": get_dealings(distributor, hotel) if hotel else None,
		"can_review": bool(hotel) and frappe.has_permission("HAT Distributor Rating", "create"),
	}


def check_access(distributor, hotel):
	if frappe.db.get_value("Supplier", distributor, "supplier_group") != "Distributor":
		frappe.throw(_("{0} is not a distributor").format(distributor), frappe.DoesNotExistError)
	roles = set(frappe.get_roles())
	if roles & STAFF_ROLES:
		return
	if "Distributor" in roles and distributor in get_user_distributors(frappe.session.user):
		return
	if hotel and (
		frappe.db.get_value("Supplier", distributor, "hat_verified")
		or frappe.db.exists("HAT Order Request", {"hotel": hotel, "distributor": distributor})
	):
		return
	frappe.throw(_("You cannot see this distributor"), frappe.PermissionError)


def get_scores(distributor):
	"""Average of each score over the ratings that gave one (0 means not given)."""
	ratings = frappe.get_all(
		"HAT Distributor Rating",
		filters={"distributor": distributor},
		fields=["rating", "quality", "delivery", "communication", "review_type"],
	)

	def average(field):
		values = [flt(r[field]) for r in ratings if flt(r[field])]
		return sum(values) / len(values) if values else None

	return {
		"count": len(ratings),
		"overall_reviews": sum(1 for r in ratings if r.review_type == "Overall"),
		**{field: average(field) for field in ("rating", "quality", "delivery", "communication")},
	}


def get_reviews(distributor):
	"""The latest ratings, public to everyone who may see the distributor, as on any marketplace."""
	reviews = frappe.get_all(
		"HAT Distributor Rating",
		filters={"distributor": distributor},
		fields=[
			"name",
			"hotel",
			"review_type",
			"rating",
			"quality",
			"delivery",
			"communication",
			"comment",
			"modified",
		],
		order_by="modified desc",
		limit=REVIEWS,
	)
	names = dict(
		frappe.get_all(
			"Customer",
			filters={"name": ("in", [r.hotel for r in reviews] or [""])},
			fields=["name", "customer_name"],
			as_list=True,
		)
	)
	for review in reviews:
		review.hotel_name = names.get(review.hotel, review.hotel)
	return reviews


def get_products(distributor):
	"""The distributor's listings this user may see (hotels: published ones), newest first."""
	filters = {"distributor": distributor}
	total = len(frappe.get_list("HAT Listing", filters=filters, pluck="name", limit_page_length=0))
	listings = frappe.get_list(
		"HAT Listing",
		filters=filters,
		fields=["name", "item", "title", "item_group", "price", "price_type", "uom", "image", "availability"],
		order_by="modified desc",
		limit_page_length=PRODUCTS,
	)
	return {"total": total, "listings": listings}


def get_dealings(distributor, hotel):
	"""What the viewing hotel has done with this distributor."""
	orders = frappe.get_list(
		"HAT Order Request",
		filters={"hotel": hotel, "distributor": distributor, "status": ("!=", "Draft")},
		fields=["name", "status", "transaction_date", "total_amount"],
		order_by="transaction_date desc",
		limit_page_length=0,
	)
	rated = set(
		frappe.get_all(
			"HAT Distributor Rating",
			filters={"hotel": hotel, "distributor": distributor, "order_request": ("is", "set")},
			pluck="order_request",
		)
	)
	completed = [o for o in orders if o.status == "Completed"]
	review = frappe.db.get_value(
		"HAT Distributor Rating",
		{"hotel": hotel, "distributor": distributor, "order_request": ("is", "not set")},
		["name", "rating", "comment"],
		as_dict=True,
	)
	return {
		"orders": len(orders),
		"ordered": sum(flt(o.total_amount) for o in orders if o.status in SALE_STATUSES),
		"last_order": orders[0].transaction_date if orders else None,
		"to_rate": [o.name for o in completed if o.name not in rated],
		"review": review,
	}
