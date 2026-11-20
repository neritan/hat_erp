"""Every listing on the marketplace: price, minimum quantity, lead time, availability and gaps
such as a missing image. Hotels see what they can buy, distributors their own listings."""

from collections import Counter

import frappe
from frappe import _

from hat.hospitality_and_tourism_academy.report.utils import child_rows, get_list


def execute(filters=None):
	filters = frappe._dict(filters or {})
	listings = get_listings(filters)
	tiers = Counter(
		row.parent
		for row in child_rows("HAT Listing Price Tier", "HAT Listing", [l.name for l in listings], [])
	)

	data = [
		{
			"listing": l.name,
			"title": l.title or l.item_name,
			"item": l.item,
			"item_group": l.item_group,
			"distributor": l.distributor,
			"distributor_name": l.distributor_name,
			"price_type": l.price_type,
			"price": l.price,
			"currency": l.currency,
			"uom": l.uom,
			"minimum_qty": l.minimum_qty,
			"lead_time_days": l.lead_time_days,
			"price_tiers": tiers.get(l.name, 0),
			"availability": l.availability,
			"published": l.published,
			"has_image": 1 if l.image else 0,
			"distributor_rating": l.distributor_rating,
		}
		for l in listings
	]
	return get_columns(), data, None, get_chart(data), get_summary(data)


def get_listings(filters):
	conditions = []
	for field in ("distributor", "availability", "price_type"):
		if filters.get(field):
			conditions.append([field, "=", filters[field]])
	if filters.get("item_group"):
		conditions.append(["item_group", "descendants of (inclusive)", filters.item_group])
	if filters.get("published") in ("Yes", "No"):
		conditions.append(["published", "=", 1 if filters.published == "Yes" else 0])
	if filters.get("missing_image"):
		conditions.append(["image", "is", "not set"])

	return get_list(
		"HAT Listing",
		fields=[
			"name",
			"title",
			"item",
			"item_name",
			"item_group",
			"distributor",
			"distributor_name",
			"price_type",
			"price",
			"currency",
			"uom",
			"minimum_qty",
			"lead_time_days",
			"availability",
			"published",
			"image",
			"distributor_rating",
		],
		filters=conditions,
		order_by="item_group asc, title asc",
	)


def get_columns():
	return [
		{
			"fieldname": "listing",
			"label": _("Listing"),
			"fieldtype": "Link",
			"options": "HAT Listing",
			"width": 110,
		},
		{"fieldname": "title", "label": _("Product"), "fieldtype": "Data", "width": 220},
		{"fieldname": "item", "label": _("Item"), "fieldtype": "Link", "options": "Item", "width": 120},
		{
			"fieldname": "item_group",
			"label": _("Category"),
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 140,
		},
		{
			"fieldname": "distributor",
			"label": _("Distributor"),
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 160,
		},
		{"fieldname": "price_type", "label": _("Price Type"), "fieldtype": "Data", "width": 120},
		{
			"fieldname": "price",
			"label": _("Price"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 110,
		},
		{"fieldname": "uom", "label": _("UOM"), "fieldtype": "Link", "options": "UOM", "width": 80},
		{"fieldname": "minimum_qty", "label": _("Minimum Qty"), "fieldtype": "Float", "width": 100},
		{"fieldname": "lead_time_days", "label": _("Lead Time (Days)"), "fieldtype": "Int", "width": 110},
		{"fieldname": "price_tiers", "label": _("Price Tiers"), "fieldtype": "Int", "width": 90},
		{"fieldname": "availability", "label": _("Availability"), "fieldtype": "Data", "width": 110},
		{"fieldname": "published", "label": _("Published"), "fieldtype": "Check", "width": 90},
		{"fieldname": "has_image", "label": _("Has Image"), "fieldtype": "Check", "width": 90},
		{"fieldname": "distributor_rating", "label": _("Rating"), "fieldtype": "Rating", "width": 110},
		{
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1,
		},
	]


def get_chart(data):
	if not data:
		return None
	top = Counter(row["item_group"] or _("No Category") for row in data).most_common(10)
	return {
		"data": {
			"labels": [label for label, _count in top],
			"datasets": [{"name": _("Listings"), "values": [count for _label, count in top]}],
		},
		"type": "bar",
		"colors": ["#2490ef"],
	}


def get_summary(data):
	return [
		{"label": _("Listings"), "value": len(data), "datatype": "Int", "indicator": "Blue"},
		{
			"label": _("Published"),
			"value": sum(1 for row in data if row["published"]),
			"datatype": "Int",
			"indicator": "Green",
		},
		{
			"label": _("Out of Stock"),
			"value": sum(1 for row in data if row["availability"] == "Out of Stock"),
			"datatype": "Int",
			"indicator": "Orange",
		},
		{
			"label": _("Without Image"),
			"value": sum(1 for row in data if not row["has_image"]),
			"datatype": "Int",
			"indicator": "Red",
		},
		{
			"label": _("Distributors"),
			"value": len({row["distributor"] for row in data}),
			"datatype": "Int",
			"indicator": "Blue",
		},
	]
