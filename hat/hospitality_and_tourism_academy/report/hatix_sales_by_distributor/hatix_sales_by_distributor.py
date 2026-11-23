"""What each distributor sold through Hatix in a period: requests received, orders accepted, value,
commission, the hotels served, the best-selling product and the distributor's rating.

A sale is an order request the distributor accepted (Accepted, Delivered or Completed)."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from hat.hospitality_and_tourism_academy.doctype.hat_partnership.hat_partnership import (
	hidden_from as partnerships_hidden,
)
from hat.hospitality_and_tourism_academy.report.utils import (
	LOST_STATUSES,
	SALE_STATUSES,
	average,
	child_rows,
	get_list,
	get_order_requests,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	orders = get_order_requests(filters)

	by_distributor = defaultdict(list)
	for order in orders:
		by_distributor[order.distributor].append(order)

	sales = [o for o in orders if o.status in SALE_STATUSES]
	sold = defaultdict(lambda: defaultdict(float))  # distributor -> item -> amount
	distributor_of = {o.name: o.distributor for o in sales}
	for row in child_rows("HAT Order Request Item", "HAT Order Request", distributor_of, ["item", "amount"]):
		if row.item:
			sold[distributor_of[row.parent]][row.item] += flt(row.amount)

	ratings = defaultdict(list)
	for rating in get_list(
		"HAT Distributor Rating",
		fields=["distributor", "rating"],
		filters=[["distributor", "in", list(by_distributor) or [""]]],
	):
		ratings[rating.distributor].append(flt(rating.rating))

	data = []
	for distributor, rows in by_distributor.items():
		won = [o for o in rows if o.status in SALE_STATUSES]
		value = sum(flt(o.total_amount) for o in won)
		top = max(sold[distributor].items(), key=lambda pair: pair[1], default=(None, 0))
		data.append(
			{
				"distributor": distributor,
				"distributor_name": rows[0].distributor_name,
				"requests": len(rows),
				"orders": len(won),
				"lost": sum(1 for o in rows if o.status in LOST_STATUSES),
				"hotels": len({o.hotel for o in won}),
				"sales": value,
				"commission": sum(flt(o.commission_amount) for o in won),
				"average_order": value / len(won) if won else 0,
				"top_item": top[0],
				"top_item_sales": top[1],
				"rating": average(ratings.get(distributor)),
			}
		)
	data.sort(key=lambda row: row["sales"], reverse=True)
	columns, summary = get_columns(), get_summary(data)
	if partnerships_hidden():
		# Commission is HAT's agreement with the distributor; hotels do not see it
		for row in data:
			row.pop("commission")
		columns = [c for c in columns if c["fieldname"] != "commission"]
		summary = [s for s in summary if s["label"] != _("Commission")]
	return columns, data, None, get_chart(data), summary


def get_columns():
	return [
		{
			"fieldname": "distributor",
			"label": _("Distributor"),
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 180,
		},
		{"fieldname": "requests", "label": _("Requests"), "fieldtype": "Int", "width": 90},
		{"fieldname": "orders", "label": _("Orders"), "fieldtype": "Int", "width": 80},
		{"fieldname": "lost", "label": _("Rejected / Cancelled"), "fieldtype": "Int", "width": 140},
		{"fieldname": "hotels", "label": _("Hotels"), "fieldtype": "Int", "width": 80},
		{"fieldname": "sales", "label": _("Sales"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "commission", "label": _("Commission"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "average_order", "label": _("Average Order"), "fieldtype": "Currency", "width": 120},
		{
			"fieldname": "top_item",
			"label": _("Best-Selling Item"),
			"fieldtype": "Link",
			"options": "Item",
			"width": 160,
		},
		{"fieldname": "top_item_sales", "label": _("Its Sales"), "fieldtype": "Currency", "width": 110},
		{"fieldname": "rating", "label": _("Rating"), "fieldtype": "Rating", "width": 110},
	]


def get_chart(data):
	top = [row for row in data if row["sales"]][:10]
	if not top:
		return None
	return {
		"data": {
			"labels": [row["distributor_name"] or row["distributor"] for row in top],
			"datasets": [{"name": _("Sales"), "values": [row["sales"] for row in top]}],
		},
		"type": "bar",
		"fieldtype": "Currency",
		"colors": ["#29cd42"],
	}


def get_summary(data):
	sales = sum(row["sales"] for row in data)
	orders = sum(row["orders"] for row in data)
	return [
		{"label": _("Sales"), "value": sales, "datatype": "Currency", "indicator": "Green"},
		{"label": _("Orders"), "value": orders, "datatype": "Int", "indicator": "Blue"},
		{
			"label": _("Commission"),
			"value": sum(row["commission"] for row in data),
			"datatype": "Currency",
			"indicator": "Blue",
		},
		{
			"label": _("Average Order"),
			"value": sales / orders if orders else 0,
			"datatype": "Currency",
			"indicator": "Blue",
		},
		{
			"label": _("Distributors with Sales"),
			"value": sum(1 for row in data if row["orders"]),
			"datatype": "Int",
			"indicator": "Blue",
		},
	]
