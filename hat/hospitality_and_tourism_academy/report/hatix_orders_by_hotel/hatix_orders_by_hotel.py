"""What each hotel ordered through Hatix in a period: requests, how many are open, delivered or
lost, the value ordered, the distributors used and the last order date.

The ordered value counts order requests a distributor accepted (Accepted, Delivered, Completed)."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from hat.hospitality_and_tourism_academy.report.utils import (
	DONE_STATUSES,
	LOST_STATUSES,
	OPEN_STATUSES,
	SALE_STATUSES,
	child_rows,
	get_order_requests,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	orders = get_order_requests(filters)

	by_hotel = defaultdict(list)
	for order in orders:
		by_hotel[order.hotel].append(order)

	hotel_of = {o.name: o.hotel for o in orders if o.status in SALE_STATUSES}
	lines = defaultdict(int)
	for row in child_rows("HAT Order Request Item", "HAT Order Request", hotel_of, []):
		lines[hotel_of[row.parent]] += 1

	data = []
	for hotel, rows in by_hotel.items():
		won = [o for o in rows if o.status in SALE_STATUSES]
		value = sum(flt(o.total_amount) for o in won)
		data.append(
			{
				"hotel": hotel,
				"hotel_name": rows[0].hotel_name,
				"requests": len(rows),
				"open": sum(1 for o in rows if o.status in OPEN_STATUSES),
				"done": sum(1 for o in rows if o.status in DONE_STATUSES),
				"lost": sum(1 for o in rows if o.status in LOST_STATUSES),
				"ordered": value,
				"average_order": value / len(won) if won else 0,
				"lines": lines.get(hotel, 0),
				"distributors": len({o.distributor for o in won}),
				"last_order": max(o.transaction_date for o in rows),
			}
		)
	data.sort(key=lambda row: row["ordered"], reverse=True)
	return get_columns(), data, None, get_chart(data), get_summary(data)


def get_columns():
	return [
		{"fieldname": "hotel", "label": _("Hotel"), "fieldtype": "Link", "options": "Customer", "width": 180},
		{"fieldname": "requests", "label": _("Requests"), "fieldtype": "Int", "width": 90},
		{"fieldname": "open", "label": _("Open"), "fieldtype": "Int", "width": 70},
		{"fieldname": "done", "label": _("Delivered / Completed"), "fieldtype": "Int", "width": 150},
		{"fieldname": "lost", "label": _("Rejected / Cancelled"), "fieldtype": "Int", "width": 140},
		{"fieldname": "ordered", "label": _("Ordered Value"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "average_order", "label": _("Average Order"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "lines", "label": _("Order Lines"), "fieldtype": "Int", "width": 100},
		{"fieldname": "distributors", "label": _("Distributors"), "fieldtype": "Int", "width": 100},
		{"fieldname": "last_order", "label": _("Last Request"), "fieldtype": "Date", "width": 110},
	]


def get_chart(data):
	top = [row for row in data if row["ordered"]][:10]
	if not top:
		return None
	return {
		"data": {
			"labels": [row["hotel_name"] or row["hotel"] for row in top],
			"datasets": [{"name": _("Ordered Value"), "values": [row["ordered"] for row in top]}],
		},
		"type": "bar",
		"fieldtype": "Currency",
		"colors": ["#2490ef"],
	}


def get_summary(data):
	return [
		{
			"label": _("Ordered Value"),
			"value": sum(row["ordered"] for row in data),
			"datatype": "Currency",
			"indicator": "Green",
		},
		{
			"label": _("Requests"),
			"value": sum(row["requests"] for row in data),
			"datatype": "Int",
			"indicator": "Blue",
		},
		{
			"label": _("Open"),
			"value": sum(row["open"] for row in data),
			"datatype": "Int",
			"indicator": "Orange",
		},
		{
			"label": _("Rejected / Cancelled"),
			"value": sum(row["lost"] for row in data),
			"datatype": "Int",
			"indicator": "Red",
		},
		{"label": _("Hotels"), "value": len(data), "datatype": "Int", "indicator": "Blue"},
	]
