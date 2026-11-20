"""What happened on Hatix each day: new listings, quote requests, quotes sent, order requests and
their value, ratings, and new hotels and distributors.

Each user counts only what they can see, so a hotel sees its own day and a distributor theirs."""

from collections import Counter, defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate

from hat.hospitality_and_tourism_academy.report.utils import SENT_QUOTE_STATUSES, date_range, get_list

COUNTS = (
	# fieldname, label (translated when shown), doctype, date field, extra filters
	("listings", "New Listings", "HAT Listing", "creation", []),
	("quote_requests", "Quote Requests", "HAT Quote Request", "creation", [["status", "!=", "Draft"]]),
	("quotes", "Quotes Sent", "HAT Quote", "creation", [["status", "in", SENT_QUOTE_STATUSES]]),
	(
		"order_requests",
		"Order Requests",
		"HAT Order Request",
		"transaction_date",
		[["status", "!=", "Draft"]],
	),
	("ratings", "Ratings", "HAT Distributor Rating", "creation", []),
	("hotels", "New Hotels", "Customer", "creation", [["customer_group", "=", "Hotel"]]),
	("distributors", "New Distributors", "Supplier", "creation", [["supplier_group", "=", "Distributor"]]),
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	from_date, to_date = date_range(filters, days=30, max_days=366)

	days = defaultdict(Counter)
	order_value = defaultdict(float)
	for fieldname, _label, doctype, date_field, extra in COUNTS:
		fields = [date_field] + (["total_amount"] if doctype == "HAT Order Request" else [])
		for row in get_list(
			doctype, fields=fields, filters=[[date_field, "between", [from_date, to_date]], *extra]
		):
			day = getdate(row[date_field])
			days[day][fieldname] += 1
			if doctype == "HAT Order Request":
				order_value[day] += flt(row.total_amount)

	data = []
	day = from_date
	while day <= to_date:
		if days[day] or not filters.get("hide_quiet_days"):
			data.append(
				{
					"date": day,
					**{fieldname: days[day][fieldname] for fieldname, *_rest in COUNTS},
					"order_value": order_value[day],
				}
			)
		day = add_days(day, 1)

	return get_columns(), data, None, get_chart(data), get_summary(data)


def get_columns():
	columns = [{"fieldname": "date", "label": _("Date"), "fieldtype": "Date", "width": 110}]
	for fieldname, label, *_rest in COUNTS:
		columns.append({"fieldname": fieldname, "label": _(label), "fieldtype": "Int", "width": 120})
		if fieldname == "order_requests":
			columns.append(
				{"fieldname": "order_value", "label": _("Order Value"), "fieldtype": "Currency", "width": 120}
			)
	return columns


def get_chart(data):
	if not data:
		return None
	return {
		"data": {
			"labels": [frappe.format(row["date"], "Date") for row in data],
			"datasets": [
				{"name": _("Quote Requests"), "values": [row["quote_requests"] for row in data]},
				{"name": _("Quotes Sent"), "values": [row["quotes"] for row in data]},
				{"name": _("Order Requests"), "values": [row["order_requests"] for row in data]},
			],
		},
		"type": "line",
		"lineOptions": {"regionFill": 1},
	}


def get_summary(data):
	summary = [
		{
			"label": _(label),
			"value": sum(row[fieldname] for row in data),
			"datatype": "Int",
			"indicator": "Blue",
		}
		for fieldname, label, *_rest in COUNTS
		if fieldname in ("listings", "quote_requests", "quotes", "order_requests")
	]
	summary.append(
		{
			"label": _("Order Value"),
			"value": sum(row["order_value"] for row in data),
			"datatype": "Currency",
			"indicator": "Green",
		}
	)
	return summary
