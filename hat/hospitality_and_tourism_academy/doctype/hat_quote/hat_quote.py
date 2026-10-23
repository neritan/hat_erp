# Copyright (c) 2026, HAT and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, now_datetime

from hat.hospitality_and_tourism_academy.doctype.hat_partnership.hat_partnership import (
	validate_party_group,
)
from hat.hospitality_and_tourism_academy.doctype.hat_quote_request.hat_quote_request import (
	get_matching_distributors,
	notify,
	users_of,
)


class HATQuote(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hat.hospitality_and_tourism_academy.doctype.hat_quote_item.hat_quote_item import HATQuoteItem

		delivery_days: DF.Int
		distributor: DF.Link
		distributor_name: DF.Data | None
		hotel: DF.Link | None
		hotel_name: DF.Data | None
		items: DF.Table[HATQuoteItem]
		notes: DF.Text | None
		quote_deadline: DF.Datetime | None
		quote_request: DF.Link
		status: DF.Literal["Draft", "Submitted", "Awarded", "Not Awarded", "Withdrawn"]
		title: DF.Data | None
		total_amount: DF.Currency
		valid_until: DF.Date | None
	# end: auto-generated types

	_DOCTYPE_NAME = "HAT Quote"

	def validate(self):
		validate_party_group("Supplier", self.distributor, "Distributor")
		request = frappe.db.get_value(
			"HAT Quote Request",
			self.quote_request,
			["hotel", "status", "quote_deadline"],
			as_dict=True,
		)
		self.hotel = request.hotel
		before = self.get_doc_before_save()
		if before and before.status in ("Awarded", "Not Awarded", "Withdrawn"):
			frappe.throw(_("A {0} quote cannot be changed").format(_(before.status)))
		self.validate_one_per_distributor()
		if self.status in ("Draft", "Submitted"):
			if request.status != "Open":
				frappe.throw(_("Quote request {0} is not open for quotes").format(self.quote_request))
			if get_datetime(request.quote_deadline) <= now_datetime():
				frappe.throw(_("The deadline for quote request {0} has passed").format(self.quote_request))
			if self.is_new() and self.distributor not in get_matching_distributors(
				frappe.get_all(
					"HAT Quote Request Item", filters={"parent": self.quote_request}, pluck="item_group"
				)
			):
				frappe.throw(
					_("{0} does not supply the products in this request, or is not verified by HAT").format(
						frappe.bold(self.distributor_name or self.distributor)
					)
				)
			self.sync_lines()
			if self.status == "Submitted":
				self.validate_has_price()
		self.calculate_totals()

	def sync_lines(self):
		"""A quote prices exactly the request's lines: add missing ones, drop the rest."""
		existing = {row.request_item: row for row in self.items if row.request_item}
		lines = get_quote_lines(self.quote_request, self.distributor)
		for line in lines:
			row = existing.get(line["request_item"])
			if row:
				line.update(can_supply=row.can_supply, rate=row.rate, remarks=row.remarks)
		self.set("items", lines)

	def validate_has_price(self):
		if not any(row.can_supply and flt(row.rate) > 0 for row in self.items):
			frappe.throw(_("Enter a price for at least one product you can supply"))

	def validate_one_per_distributor(self):
		other = frappe.db.exists(
			"HAT Quote",
			{
				"quote_request": self.quote_request,
				"distributor": self.distributor,
				"status": ("!=", "Withdrawn"),
				"name": ("!=", self.name),
			},
		)
		if other and self.status != "Withdrawn":
			frappe.throw(
				_("{0} has already quoted on this request: {1}").format(self.distributor_name, other)
			)

	def calculate_totals(self):
		for row in self.items:
			if not row.can_supply:
				row.rate = 0
			row.amount = flt(row.qty) * flt(row.rate)
		self.total_amount = sum(flt(row.amount) for row in self.items)

	def on_update(self):
		update_quote_count(self.quote_request)

	def on_trash(self):
		update_quote_count(self.quote_request, exclude=self.name)

	@frappe.whitelist()
	def submit_quote(self) -> None:
		self.check_permission("write")
		if self.status != "Draft":
			frappe.throw(_("Only a Draft quote can be submitted"))
		self.status = "Submitted"
		self.save()
		request = frappe.get_doc("HAT Quote Request", self.quote_request)
		notify(
			users_of("Customer", [request.hotel]),
			request,
			_("New quote from {0} for {1}").format(self.distributor_name, request.title),
		)

	@frappe.whitelist()
	def withdraw(self) -> None:
		self.check_permission("write")
		if self.status not in ("Draft", "Submitted"):
			frappe.throw(_("A {0} quote cannot be withdrawn").format(_(self.status)))
		self.status = "Withdrawn"
		self.save()


@frappe.whitelist()
def get_quote_lines(quote_request: str, distributor: str | None = None) -> list[dict]:
	"""The request's lines, priced from the distributor's marketplace listings where it has one."""
	frappe.get_doc("HAT Quote Request", quote_request).check_permission("read")
	prices = {}
	if distributor:
		prices = dict(
			frappe.get_all(
				"HAT Listing",
				filters={"distributor": distributor, "price_type": "Fixed Price"},
				fields=["item", "price"],
				as_list=True,
			)
		)
	return [
		{
			"request_item": row.name,
			"item": row.item,
			"item_group": row.item_group,
			"description": row.description,
			"qty": row.qty,
			"uom": row.uom,
			"can_supply": 1,
			"rate": prices.get(row.item) if row.item else None,
		}
		for row in frappe.get_all(
			"HAT Quote Request Item",
			filters={"parent": quote_request, "parenttype": "HAT Quote Request"},
			fields=["name", "item", "item_group", "description", "qty", "uom"],
			order_by="idx",
		)
	]


def update_quote_count(quote_request, exclude=None):
	filters = {"quote_request": quote_request, "status": ("in", ("Submitted", "Awarded", "Not Awarded"))}
	if exclude:
		filters["name"] = ("!=", exclude)
	frappe.db.set_value(
		"HAT Quote Request", quote_request, "quote_count", frappe.db.count("HAT Quote", filters)
	)
