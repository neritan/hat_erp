# Copyright (c) 2026, HAT and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, flt, get_datetime, now_datetime, nowdate
from frappe.utils.nestedset import get_ancestors_of, get_descendants_of

from hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing import (
	STAFF_ROLES,
	is_hotel_only,
	resolve_hotel,
)
from hat.hospitality_and_tourism_academy.doctype.hat_partnership.hat_partnership import (
	validate_party_group,
)

LINE_FIELDS = ("item", "item_group", "description", "qty", "uom")


class HATQuoteRequest(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hat.hospitality_and_tourism_academy.doctype.hat_quote_request_item.hat_quote_request_item import (
			HATQuoteRequestItem,
		)

		delivery_address: DF.Link | None
		hotel: DF.Link
		hotel_city: DF.Data | None
		hotel_name: DF.Data | None
		hotel_stars: DF.Data | None
		items: DF.Table[HATQuoteRequestItem]
		notes: DF.Text | None
		quote_count: DF.Int
		quote_deadline: DF.Datetime
		required_by: DF.Date | None
		status: DF.Literal["Draft", "Open", "Closed", "Awarded", "Cancelled"]
		territory: DF.Link | None
		title: DF.Data
	# end: auto-generated types

	_DOCTYPE_NAME = "HAT Quote Request"

	def validate(self):
		validate_party_group("Customer", self.hotel, "Hotel")
		if not self.items:
			frappe.throw(_("Add at least one product"))
		for row in self.items:
			if frappe.db.get_value("Item Group", row.item_group, "is_group"):
				frappe.throw(
					_("Row {0}: {1} is a category; choose one of its product groups").format(
						row.idx, frappe.bold(row.item_group)
					)
				)
			if flt(row.qty) <= 0:
				frappe.throw(_("Row {0}: enter a quantity").format(row.idx))
		self.validate_lines_locked()

	def validate_lines_locked(self):
		"""Distributors quote on the lines as published, so they only change while Draft."""
		before = self.get_doc_before_save()
		if not before or before.status == "Draft":
			return
		if lines(before) != lines(self):
			frappe.throw(_("Products can only be changed while the request is a Draft"))

	@frappe.whitelist()
	def publish(self) -> None:
		self.check_permission("write")
		if self.status != "Draft":
			frappe.throw(_("Only a Draft request can be published"))
		if get_datetime(self.quote_deadline) <= now_datetime():
			frappe.throw(_("Set Quotes Due By to a time in the future"))
		self.status = "Open"
		self.save()
		distributors = get_matching_distributors([row.item_group for row in self.items])
		notify(
			users_of("Supplier", distributors),
			self,
			_("New quote request from {0}: {1}").format(self.hotel_name, self.title),
		)
		frappe.msgprint(
			_("Published to {0} matching distributors").format(len(distributors)),
			alert=True,
			indicator="green",
		)

	@frappe.whitelist()
	def close(self) -> None:
		self.check_permission("write")
		if self.status != "Open":
			frappe.throw(_("Only an Open request can be closed"))
		self.status = "Closed"
		self.save()

	@frappe.whitelist()
	def cancel_request(self) -> None:
		self.check_permission("write")
		if self.status not in ("Draft", "Open", "Closed"):
			frappe.throw(_("A {0} request cannot be cancelled").format(_(self.status)))
		self.status = "Cancelled"
		self.save()

	@frappe.whitelist()
	def get_comparison(self) -> dict:
		"""Submitted quotes with their rate per request line, for the hotel to compare."""
		self.check_permission("write")
		quotes = frappe.get_all(
			"HAT Quote",
			filters={"quote_request": self.name, "status": ("in", ("Submitted", "Awarded", "Not Awarded"))},
			fields=[
				"name",
				"distributor",
				"distributor_name",
				"delivery_days",
				"valid_until",
				"total_amount",
			],
			order_by="total_amount asc",
		)
		rates = get_quote_rates([q.name for q in quotes])
		for quote in quotes:
			quote.rating = frappe.db.get_value("Supplier", quote.distributor, "hat_average_rating")
			quote.rates = {line: rate for (name, line), rate in rates.items() if name == quote.name}
		return {
			"lines": [
				{
					"name": row.name,
					"description": row.description,
					"qty": row.qty,
					"uom": row.uom,
					"awarded_quote": row.awarded_quote,
				}
				for row in self.items
			],
			"quotes": quotes,
		}

	@frappe.whitelist()
	def award(self, awards: dict) -> list[str]:
		"""Award each line to a submitted quote ({line name: quote name}) and send one order per winner."""
		self.check_permission("write")
		if self.status not in ("Open", "Closed"):
			frappe.throw(_("Only an Open or Closed request can be awarded"))
		quotes = {
			q.name: q
			for q in frappe.get_all(
				"HAT Quote",
				filters={"quote_request": self.name, "status": "Submitted"},
				fields=["name", "distributor"],
			)
		}
		rates = get_quote_rates(list(quotes))
		won = {}
		for row in self.items:
			quote = awards.get(row.name)
			if not quote:
				continue
			if quote not in quotes:
				frappe.throw(
					_("Row {0}: {1} is not a submitted quote for this request").format(row.idx, quote)
				)
			if not rates.get((quote, row.name)):
				frappe.throw(_("Row {0}: quote {1} has no price for this product").format(row.idx, quote))
			row.awarded_quote = quote
			row.awarded_distributor = quotes[quote].distributor
			row.awarded_rate = rates[(quote, row.name)]
			won.setdefault(quote, []).append(row)
		if not won:
			frappe.throw(_("Choose a quote for at least one product"))

		self.status = "Awarded"
		# the hotel may not write the award fields directly; this method sets them
		self.flags.ignore_permissions = True
		self.save()

		orders = [self.make_order(quotes[quote], rows) for quote, rows in won.items()]
		for name, quote in quotes.items():
			frappe.db.set_value("HAT Quote", name, "status", "Awarded" if name in won else "Not Awarded")
			notify(
				users_of("Supplier", [quote.distributor]),
				frappe.get_doc("HAT Quote", name),
				_("{0}: your quote was awarded").format(self.title)
				if name in won
				else _("{0}: your quote was not selected").format(self.title),
			)
		return orders

	def make_order(self, quote, rows):
		order = frappe.new_doc("HAT Order Request")
		order.update(
			{
				"request_type": "Order",
				"hotel": self.hotel,
				"distributor": quote.distributor,
				"required_by": self.required_by,
				"delivery_address": self.delivery_address,
				"quote_request": self.name,
				"quote": quote.name,
				"notes": _("Awarded from quote request {0}").format(self.name),
			}
		)
		for row in rows:
			order.append(
				"items",
				{
					"item": row.item,
					"item_group": row.item_group,
					"description": row.description,
					"qty": row.qty,
					"uom": row.uom,
					"rate": row.awarded_rate,
				},
			)
		order.insert()
		apply_workflow(order, "Send to Distributor")
		return order.name


def lines(doc):
	return [tuple(row.get(f) for f in LINE_FIELDS) for row in doc.items]


def get_quote_rates(quotes):
	"""{(quote, request line): rate} for the lines each quote can supply."""
	if not quotes:
		return {}
	return {
		(row.parent, row.request_item): flt(row.rate)
		for row in frappe.get_all(
			"HAT Quote Item",
			filters={"parent": ("in", quotes), "parenttype": "HAT Quote", "can_supply": 1, "rate": (">", 0)},
			fields=["parent", "request_item", "rate"],
		)
	}


def get_matching_distributors(item_groups):
	"""Verified distributors that supply any of these product groups: by Categories Supplied
	(the group or a parent of it) or by a listing in the group."""
	groups = {g for group in item_groups for g in (group, *get_ancestors_of("Item Group", group))}
	candidates = set(
		frappe.get_all(
			"HAT Category",
			filters={"parenttype": "Supplier", "item_group": ("in", list(groups))},
			pluck="parent",
		)
	) | set(
		frappe.get_all("HAT Listing", filters={"item_group": ("in", list(item_groups))}, pluck="distributor")
	)
	if not candidates:
		return []
	return frappe.get_all(
		"Supplier",
		filters={
			"name": ("in", list(candidates)),
			"supplier_group": "Distributor",
			"hat_verified": 1,
			"disabled": 0,
		},
		pluck="name",
	)


def get_distributor_groups(distributor):
	"""Every product group a distributor can quote on."""
	groups = set(frappe.get_all("HAT Listing", filters={"distributor": distributor}, pluck="item_group"))
	for category in frappe.get_all(
		"HAT Category", filters={"parenttype": "Supplier", "parent": distributor}, pluck="item_group"
	):
		groups.add(category)
		groups.update(get_descendants_of("Item Group", category))
	return groups


def users_of(doctype, names):
	"""Enabled users linked to these customers / suppliers through User Permissions."""
	if not names:
		return []
	users = frappe.get_all(
		"User Permission", filters={"allow": doctype, "for_value": ("in", list(names))}, pluck="user"
	)
	return frappe.get_all("User", filters={"name": ("in", users or [""]), "enabled": 1}, pluck="name")


def notify(users, doc, subject):
	for user in set(users) - {frappe.session.user}:
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"from_user": frappe.session.user,
				"type": "Alert",
				"document_type": doc.doctype,
				"document_name": doc.name,
				"subject": subject,
			}
		).insert(ignore_permissions=True)


def get_user_distributors(user):
	return frappe.get_all("User Permission", filters={"user": user, "allow": "Supplier"}, pluck="for_value")


def is_distributor_only(user):
	roles = set(frappe.get_roles(user))
	return "Distributor" in roles and not roles & STAFF_ROLES


@frappe.whitelist()
def make_quote(quote_request: str, distributor: str | None = None) -> str:
	"""The distributor's quote for a request: the existing one, or a new draft pre-filled with
	the distributor's marketplace prices."""
	request = frappe.get_doc("HAT Quote Request", quote_request)
	request.check_permission("read")
	if not distributor:
		distributors = get_user_distributors(frappe.session.user)
		if len(distributors) != 1:
			frappe.throw(_("Select the distributor to quote for"))
		distributor = distributors[0]
	existing = frappe.db.get_value(
		"HAT Quote",
		{"quote_request": quote_request, "distributor": distributor, "status": ("!=", "Withdrawn")},
	)
	if existing:
		return existing
	quote = frappe.new_doc("HAT Quote")
	quote.update(
		{
			"quote_request": quote_request,
			"distributor": distributor,
			"delivery_days": frappe.db.get_value(
				"HAT Listing", {"distributor": distributor}, "lead_time_days"
			),
			"valid_until": add_days(nowdate(), 30),
		}
	)
	# HATQuote.sync_lines copies the request's lines, priced from the distributor's listings
	quote.insert()
	return quote.name


@frappe.whitelist(methods=["POST"])
def add_to_quote_request(item: str, qty: float, hotel: str | None = None) -> str:
	"""Add a product to the hotel's draft quote request, creating it if needed."""
	hotel = resolve_hotel(hotel)
	if not hotel:
		frappe.throw(_("Select the hotel you are asking for"))
	draft = frappe.get_list(
		"HAT Quote Request",
		filters={"hotel": hotel, "status": "Draft"},
		pluck="name",
		order_by="creation desc",
		limit=1,
	)
	if draft:
		request = frappe.get_doc("HAT Quote Request", draft[0])
	else:
		request = frappe.new_doc("HAT Quote Request")
		request.update(
			{
				"hotel": hotel,
				"title": _("Quote request {0}").format(frappe.format(nowdate(), "Date")),
				"quote_deadline": add_days(now_datetime(), 3),
			}
		)
	row = next((r for r in request.items if r.item == item), None)
	if row:
		row.qty = flt(row.qty) + flt(qty)
	else:
		values = frappe.db.get_value("Item", item, ["item_name", "item_group", "stock_uom"], as_dict=True)
		request.append(
			"items",
			{
				"item": item,
				"item_group": values.item_group,
				"description": values.item_name,
				"qty": flt(qty),
				"uom": values.stock_uom,
			},
		)
	request.save()
	return request.name


def close_expired_requests():
	"""Hourly: stop taking quotes once the deadline has passed."""
	for name in frappe.get_all(
		"HAT Quote Request", filters={"status": "Open", "quote_deadline": ("<", now_datetime())}, pluck="name"
	):
		frappe.db.set_value("HAT Quote Request", name, "status", "Closed")


def get_permission_query_conditions(user=None):
	"""Distributors see published requests in their product groups, and any request they quoted."""
	user = user or frappe.session.user
	if not is_distributor_only(user):
		return ""
	distributors = get_user_distributors(user)
	if not distributors:
		return "1=0"
	quoted = (
		"`tabHAT Quote Request`.name in (select quote_request from `tabHAT Quote` where distributor in ({}))"
	).format(", ".join(frappe.db.escape(d) for d in distributors))
	verified = [d for d in distributors if frappe.db.get_value("Supplier", d, "hat_verified")]
	groups = {g for d in verified for g in get_distributor_groups(d)}
	if not groups:
		return f"({quoted})"
	matching = (
		"`tabHAT Quote Request`.status in ('Open', 'Closed', 'Awarded') and exists (select 1 from "
		"`tabHAT Quote Request Item` qri where qri.parent = `tabHAT Quote Request`.name and qri.item_group in ({}))"
	).format(", ".join(frappe.db.escape(g) for g in groups))
	return f"(({matching}) or ({quoted}))"


def has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if not is_distributor_only(user):
		return True
	distributors = get_user_distributors(user)
	if frappe.db.exists(
		"HAT Quote", {"quote_request": doc.name, "distributor": ("in", distributors or [""])}
	):
		return True
	if doc.status not in ("Open", "Closed", "Awarded"):
		return False
	requested = {row.item_group for row in doc.items}
	return any(
		frappe.db.get_value("Supplier", d, "hat_verified") and requested & get_distributor_groups(d)
		for d in distributors
	)


def get_quote_permission_query_conditions(user=None):
	"""Hotels see quotes once submitted, never a distributor's draft."""
	user = user or frappe.session.user
	if is_hotel_only(user):
		return "`tabHAT Quote`.status != 'Draft'"
	return ""


def has_quote_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if is_hotel_only(user):
		return doc.status != "Draft"
	return True
