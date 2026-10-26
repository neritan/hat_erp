"""The hotel's cart: its Draft HAT Order Requests, one per distributor, shared by all its users."""

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow
from frappe.utils import flt

from hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing import get_user_hotel
from hat.hospitality_and_tourism_academy.doctype.hat_order_request.hat_order_request import (
	minimum_order_warning,
)


def resolve_hotel(hotel=None):
	hotel = hotel or get_user_hotel()
	if not hotel:
		frappe.throw(_("Select the hotel whose cart you want to see"))
	return hotel


def get_draft_orders(hotel):
	return frappe.get_list(
		"HAT Order Request",
		filters={"hotel": hotel, "status": "Draft"},
		pluck="name",
		order_by="creation asc",
	)


@frappe.whitelist()
def get_cart(hotel: str | None = None) -> dict:
	hotel = resolve_hotel(hotel)
	parts = []
	for name in get_draft_orders(hotel):
		order = frappe.get_doc("HAT Order Request", name)
		listings = {
			row.name: row
			for row in frappe.get_all(
				"HAT Listing",
				filters={"name": ("in", [i.listing for i in order.items if i.listing] or [""])},
				fields=["name", "image", "minimum_qty", "availability", "published"],
			)
		}
		minimum = flt(frappe.db.get_value("Supplier", order.distributor, "hat_minimum_order"))
		lines = []
		for item in order.items:
			listing = listings.get(item.listing) or {}
			lines.append(
				{
					"name": item.name,
					"listing": item.listing,
					"item": item.item,
					"description": item.description,
					"qty": item.qty,
					"uom": item.uom,
					"rate": item.rate,
					"amount": item.amount,
					"image": listing.get("image"),
					"minimum_qty": listing.get("minimum_qty") or 1,
					"unavailable": bool(listing)
					and (not listing.get("published") or listing.get("availability") != "Available"),
				}
			)
		parts.append(
			{
				"order": order.name,
				"distributor": order.distributor,
				"distributor_name": order.distributor_name,
				"rating": frappe.db.get_value("Supplier", order.distributor, "hat_average_rating"),
				"request_type": order.request_type,
				"partnership": order.partnership,
				"total": order.total_amount,
				"minimum_order": minimum,
				"missing": max(minimum - flt(order.total_amount), 0) if minimum else 0,
				"lines": lines,
			}
		)
	return {
		"hotel": hotel,
		"hotel_name": frappe.db.get_value("Customer", hotel, "customer_name"),
		"parts": parts,
		"total": sum(flt(p["total"]) for p in parts),
		"count": sum(len(p["lines"]) for p in parts),
	}


@frappe.whitelist()
def get_cart_count(hotel: str | None = None) -> int:
	hotel = hotel or get_user_hotel()
	if not hotel:
		return 0
	orders = get_draft_orders(hotel)
	if not orders:
		return 0
	return frappe.db.count(
		"HAT Order Request Item", {"parent": ("in", orders), "parenttype": "HAT Order Request"}
	)


@frappe.whitelist(methods=["POST"])
def update_line(order: str, line: str, qty: float) -> None:
	"""Change a line's quantity; zero removes it, and an order left empty leaves the cart."""
	doc = get_cart_order(order)
	row = next((r for r in doc.items if r.name == line), None)
	if not row:
		frappe.throw(_("This product is no longer in the cart"))
	if flt(qty) <= 0:
		doc.remove(row)
	else:
		row.qty = flt(qty)
	if doc.items:
		doc.save()
	else:
		frappe.delete_doc("HAT Order Request", doc.name)


@frappe.whitelist(methods=["POST"])
def remove_line(order: str, line: str) -> None:
	update_line(order, line, 0)


@frappe.whitelist(methods=["POST"])
def place_order(
	hotel: str | None = None,
	orders: list | None = None,
	required_by: str | None = None,
	delivery_address: str | None = None,
	notes: str | None = None,
) -> dict:
	"""Send the cart's drafts (or only `orders`) to their distributors, each on its own."""
	hotel = resolve_hotel(hotel)
	drafts = get_draft_orders(hotel)
	selected = [o for o in drafts if not orders or o in orders]
	if not selected:
		frappe.throw(_("The cart is empty"))
	sent, failed, warnings = [], [], []
	for name in selected:
		frappe.db.savepoint("hat_place_order")
		try:
			doc = get_cart_order(name)
			doc.update(
				{
					"required_by": required_by or doc.required_by,
					"delivery_address": delivery_address or doc.delivery_address,
					"notes": "\n".join(filter(None, [doc.notes, notes])) or None,
				}
			)
			doc.save()
			apply_workflow(doc, "Send to Distributor")
			sent.append({"order": name, "distributor_name": doc.distributor_name, "total": doc.total_amount})
			warning = minimum_order_warning(doc)
			if warning:
				warnings.append(warning)
		except frappe.ValidationError as e:
			frappe.db.rollback(save_point="hat_place_order")
			failed.append(
				{
					"order": name,
					"distributor_name": frappe.db.get_value("HAT Order Request", name, "distributor_name"),
					"error": str(e) or _("Could not be sent"),
				}
			)
			frappe.clear_messages()
	return {"sent": sent, "failed": failed, "warnings": warnings}


def get_cart_order(name):
	doc = frappe.get_doc("HAT Order Request", name)
	doc.check_permission("write")
	if doc.status != "Draft":
		frappe.throw(_("Order {0} has already been sent").format(name))
	return doc
