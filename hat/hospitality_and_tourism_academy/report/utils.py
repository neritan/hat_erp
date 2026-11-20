"""Shared helpers for the Hatix reports.

Every report reads through `frappe.get_list`, so it shows what the user may see in the desk: HAT
staff see everything, a hotel only its own requests and orders (its User Permission on Customer)
and a distributor only their own quotes and orders (their User Permission on Supplier), plus the
doctypes' own rules (hotels see published listings of verified distributors, never a draft quote).
"""

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

# Order request statuses: a sale is an order the distributor accepted
SALE_STATUSES = ("Accepted", "Delivered", "Completed")
OPEN_STATUSES = ("Sent", "Quoted", "Accepted")
DONE_STATUSES = ("Delivered", "Completed")
LOST_STATUSES = ("Rejected", "Cancelled")
# Quotes a distributor actually sent
SENT_QUOTE_STATUSES = ("Submitted", "Awarded", "Not Awarded")


def date_range(filters, days: int = 30, max_days: int | None = None):
	"""The From/To Date filters, defaulting to the last `days` days."""
	to_date = getdate(filters.get("to_date") or today())
	from_date = getdate(filters.get("from_date") or add_days(to_date, -days))
	if from_date > to_date:
		frappe.throw(_("From Date must be on or before To Date"))
	if max_days and (to_date - from_date).days > max_days:
		frappe.throw(_("Choose a period of at most {0} days").format(max_days))
	return from_date, to_date


def get_list(doctype: str, **kwargs) -> list:
	"""`frappe.get_list` (the user's permissions apply), or nothing for a doctype they cannot read."""
	if not frappe.has_permission(doctype, "read"):
		return []
	return frappe.get_list(doctype, limit_page_length=0, **kwargs)


def child_rows(doctype: str, parenttype: str, parents, fields: list[str]) -> list:
	"""Rows of a child table, for parents the user was already allowed to read."""
	parents = list(parents)
	if not parents:
		return []
	return frappe.get_all(
		doctype,
		filters={"parenttype": parenttype, "parent": ("in", parents)},
		fields=["parent", *fields],
		order_by="idx asc",
	)


def average(values):
	values = [v for v in values or () if v is not None]
	return sum(values) / len(values) if values else None


def get_order_requests(filters, extra_fields=()):
	"""Order requests in the period (by their date), drafts left out: a draft is still a cart."""
	from_date, to_date = date_range(filters, days=90)
	conditions = [["transaction_date", "between", [from_date, to_date]], ["status", "!=", "Draft"]]
	for field in ("hotel", "distributor", "status"):
		if filters.get(field):
			conditions.append([field, "=", filters[field]])
	return get_list(
		"HAT Order Request",
		fields=[
			"name",
			"hotel",
			"hotel_name",
			"distributor",
			"distributor_name",
			"status",
			"transaction_date",
			"total_amount",
			"commission_amount",
			*extra_fields,
		],
		filters=conditions,
		order_by="transaction_date asc",
	)
