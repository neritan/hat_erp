"""The hotel's cart: its Draft HAT Order Requests, one per distributor, shared by all its users."""

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow
from frappe.utils import flt

from hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing import resolve_hotel
from hat.hospitality_and_tourism_academy.doctype.hat_order_request.hat_order_request import (
	minimum_order_warning,
)


def resolve_cart_hotel(hotel=None):
	hotel = resolve_hotel(hotel)
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
	"""The cart in a fixed number of queries, however many distributors and lines it holds."""
	hotel = resolve_cart_hotel(hotel)
	# get_list applies the hotel's permissions; the batched reads below only follow these orders
	orders = frappe.get_list(
		"HAT Order Request",
		filters={"hotel": hotel, "status": "Draft"},
		fields=["name", "distributor", "distributor_name", "request_type", "partnership", "total_amount"],
		order_by="creation asc",
	)
	items = {}
	for item in frappe.get_all(
		"HAT Order Request Item",
		filters={"parent": ("in", [o.name for o in orders] or [""]), "parenttype": "HAT Order Request"},
		fields=["name", "parent", "listing", "item", "description", "qty", "uom", "rate", "amount"],
		order_by="idx asc",
	):
		items.setdefault(item.parent, []).append(item)
	listings = by_name(
		"HAT Listing",
		{i.listing for rows in items.values() for i in rows if i.listing},
		["image", "minimum_qty", "availability", "published"],
	)
	suppliers = by_name(
		"Supplier", {o.distributor for o in orders}, ["hat_minimum_order", "hat_average_rating"]
	)

	parts = []
	for order in orders:
		supplier = suppliers.get(order.distributor) or {}
		minimum = flt(supplier.get("hat_minimum_order"))
		lines = []
		for item in items.get(order.name, []):
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
					# a line from a listing that was deleted, unpublished or ran out of stock
					"unavailable": bool(item.listing)
					and (
						not listing
						or not listing.get("published")
						or listing.get("availability") != "Available"
					),
				}
			)
		parts.append(
			{
				"order": order.name,
				"distributor": order.distributor,
				"distributor_name": order.distributor_name,
				"rating": supplier.get("hat_average_rating"),
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


def by_name(doctype, names, fields):
	"""{name: row} for these records in one query."""
	if not names:
		return {}
	return {
		row.name: row
		for row in frappe.get_all(doctype, filters={"name": ("in", list(names))}, fields=["name", *fields])
	}


@frappe.whitelist()
def get_cart_count(hotel: str | None = None) -> int:
	hotel = resolve_hotel(hotel)
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
	hotel = resolve_cart_hotel(hotel)
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
		except Exception as e:
			# The database undoes the whole transaction on these, savepoint included: fail it all
			if is_database_failure(e):
				raise
			frappe.db.rollback(save_point="hat_place_order")
			if isinstance(e, frappe.ValidationError | frappe.PermissionError):
				error = str(e) or _("Could not be sent")
			else:
				frappe.log_error(
					title=_("Placing order {0} failed").format(name),
					reference_doctype="HAT Order Request",
					reference_name=name,
				)
				error = _("Unexpected error; HAT support can see it in the Error Log")
			failed.append(
				{
					"order": name,
					"distributor_name": frappe.db.get_value("HAT Order Request", name, "distributor_name"),
					"error": error,
				}
			)
			frappe.clear_messages()
	return {"sent": sent, "failed": failed, "warnings": warnings}


def is_database_failure(e):
	return isinstance(
		e,
		frappe.QueryDeadlockError
		| frappe.QueryTimeoutError
		| frappe.db.OperationalError
		| frappe.db.InternalError
		| frappe.db.InterfaceError,
	)


def get_cart_order(name):
	doc = frappe.get_doc("HAT Order Request", name)
	doc.check_permission("write")
	if doc.status != "Draft":
		frappe.throw(_("Order {0} has already been sent").format(name))
	return doc
