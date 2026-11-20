"""Quote requests (RFQs) and the quotes they got: how many, how fast, the lowest, who won.

A distributor sees the requests open to them, with their own quotes only."""

from collections import Counter, defaultdict

import frappe
from frappe import _
from frappe.utils import flt, get_datetime

from hat.hospitality_and_tourism_academy.report.utils import (
	SENT_QUOTE_STATUSES,
	average,
	child_rows,
	date_range,
	get_list,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	requests = get_requests(filters)
	names = [r.name for r in requests]
	quotes = defaultdict(list)
	if names:
		for quote in get_list(
			"HAT Quote",
			fields=["name", "quote_request", "distributor_name", "status", "total_amount", "creation"],
			filters=[["quote_request", "in", names], ["status", "in", SENT_QUOTE_STATUSES]],
		):
			quotes[quote.quote_request].append(quote)
	items = Counter(
		row.parent for row in child_rows("HAT Quote Request Item", "HAT Quote Request", names, [])
	)

	data = []
	for r in requests:
		received = quotes.get(r.name, [])
		first = min((get_datetime(q.creation) for q in received), default=None)
		data.append(
			{
				"quote_request": r.name,
				"title": r.title,
				"hotel": r.hotel,
				"hotel_name": r.hotel_name,
				"status": r.status,
				"creation": r.creation,
				"quote_deadline": r.quote_deadline,
				"items": items.get(r.name, 0),
				"quotes": len(received),
				"lowest_quote": min((flt(q.total_amount) for q in received), default=None),
				"first_quote_hours": (
					round((first - get_datetime(r.creation)).total_seconds() / 3600, 1) if first else None
				),
				"awarded_to": ", ".join(
					sorted(
						{q.distributor_name for q in received if q.status == "Awarded" and q.distributor_name}
					)
				),
			}
		)
	return get_columns(), data, None, get_chart(data), get_summary(data)


def get_requests(filters):
	from_date, to_date = date_range(filters, days=90)
	conditions = [["creation", "between", [from_date, to_date]]]
	if filters.get("hotel"):
		conditions.append(["hotel", "=", filters.hotel])
	if filters.get("status"):
		conditions.append(["status", "=", filters.status])
	return get_list(
		"HAT Quote Request",
		fields=["name", "title", "hotel", "hotel_name", "status", "creation", "quote_deadline"],
		filters=conditions,
		order_by="creation desc",
	)


def get_columns():
	return [
		{
			"fieldname": "quote_request",
			"label": _("Quote Request"),
			"fieldtype": "Link",
			"options": "HAT Quote Request",
			"width": 130,
		},
		{"fieldname": "title", "label": _("Title"), "fieldtype": "Data", "width": 200},
		{"fieldname": "hotel", "label": _("Hotel"), "fieldtype": "Link", "options": "Customer", "width": 160},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 100},
		{"fieldname": "creation", "label": _("Created"), "fieldtype": "Datetime", "width": 150},
		{"fieldname": "quote_deadline", "label": _("Quotes Due By"), "fieldtype": "Datetime", "width": 150},
		{"fieldname": "items", "label": _("Items"), "fieldtype": "Int", "width": 70},
		{"fieldname": "quotes", "label": _("Quotes"), "fieldtype": "Int", "width": 80},
		{"fieldname": "lowest_quote", "label": _("Lowest Quote"), "fieldtype": "Currency", "width": 120},
		{
			"fieldname": "first_quote_hours",
			"label": _("First Quote After (Hours)"),
			"fieldtype": "Float",
			"precision": 1,
			"width": 160,
		},
		{"fieldname": "awarded_to", "label": _("Awarded To"), "fieldtype": "Data", "width": 180},
	]


def get_chart(data):
	if not data:
		return None
	statuses = Counter(row["status"] for row in data)
	return {
		"data": {
			"labels": [_(status) for status in statuses],
			"datasets": [{"name": _("Quote Requests"), "values": list(statuses.values())}],
		},
		"type": "donut",
	}


def get_summary(data):
	return [
		{"label": _("Quote Requests"), "value": len(data), "datatype": "Int", "indicator": "Blue"},
		{
			"label": _("Open"),
			"value": sum(1 for row in data if row["status"] == "Open"),
			"datatype": "Int",
			"indicator": "Orange",
		},
		{
			"label": _("Awarded"),
			"value": sum(1 for row in data if row["status"] == "Awarded"),
			"datatype": "Int",
			"indicator": "Green",
		},
		{
			"label": _("Without Quotes"),
			"value": sum(1 for row in data if row["status"] != "Draft" and not row["quotes"]),
			"datatype": "Int",
			"indicator": "Red",
		},
		{
			"label": _("Quotes per Request"),
			"value": flt(average([row["quotes"] for row in data if row["status"] != "Draft"]), 1),
			"datatype": "Float",
			"indicator": "Blue",
		},
		{
			"label": _("Hours to First Quote"),
			"value": flt(average([row["first_quote_hours"] for row in data]), 1),
			"datatype": "Float",
			"indicator": "Blue",
		},
	]
