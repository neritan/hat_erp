# Copyright (c) 2026, HAT and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from hat.hospitality_and_tourism_academy.doctype.hat_partnership.hat_partnership import (
	get_active_partnership,
	validate_party_group,
)


class HATOrderRequest(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hat.hospitality_and_tourism_academy.doctype.hat_order_request_item.hat_order_request_item import (
			HATOrderRequestItem,
		)

		commission_amount: DF.Currency
		commission_type: DF.Data | None
		delivery_address: DF.Link | None
		distributor: DF.Link
		distributor_name: DF.Data | None
		hotel: DF.Link
		hotel_name: DF.Data | None
		items: DF.Table[HATOrderRequestItem]
		notes: DF.Text | None
		partnership: DF.Link | None
		request_type: DF.Literal["Request for Quotation", "Order"]
		required_by: DF.Date | None
		status: DF.Literal[
			"Draft", "Sent", "Quoted", "Accepted", "Delivered", "Completed", "Rejected", "Cancelled"
		]
		total_amount: DF.Currency
		transaction_date: DF.Date
	# end: auto-generated types

	_DOCTYPE_NAME = "HAT Order Request"

	def validate(self):
		validate_party_group("Customer", self.hotel, "Hotel")
		validate_party_group("Supplier", self.distributor, "Distributor")
		if self.status == "Draft":
			self.validate_listings()
		self.calculate_totals()
		self.set_partnership_and_commission()
		if self.status in ("Quoted", "Accepted", "Delivered", "Completed"):
			self.validate_rates()
		if self.status == "Sent" and self.has_value_changed("status"):
			self.warn_unavailable_listings()
		if self.is_new() or self.has_value_changed("distributor") or self.has_value_changed("hotel"):
			self.warn_if_outside_coverage()

	def validate_listings(self):
		"""Marketplace lines: listing must belong to the distributor and meet its minimum quantity.

		A request made only of listings is an Order, or a Request for Quotation if any is priced on request."""
		price_types = set()
		for item in self.items:
			if not item.listing:
				continue
			listing = frappe.db.get_value(
				"HAT Listing",
				item.listing,
				["title", "distributor", "minimum_qty", "price_type"],
				as_dict=True,
			)
			if listing.distributor != self.distributor:
				frappe.throw(
					_("Row {0}: {1} is not a listing of {2}").format(
						item.idx,
						frappe.bold(listing.title),
						frappe.bold(self.distributor_name or self.distributor),
					)
				)
			if flt(item.qty) < flt(listing.minimum_qty):
				frappe.throw(
					_("Row {0}: the minimum order for {1} is {2}").format(
						item.idx, frappe.bold(listing.title), listing.minimum_qty
					)
				)
			price_types.add(listing.price_type)
		if price_types and all(item.listing for item in self.items):
			self.request_type = "Request for Quotation" if "Price on Request" in price_types else "Order"

	def warn_unavailable_listings(self):
		unavailable = [
			item.description
			for item in self.items
			if item.listing
			and frappe.db.get_value("HAT Listing", item.listing, ["published", "availability"])
			!= (1, "Available")
		]
		if unavailable:
			frappe.msgprint(
				_("No longer available on the marketplace: {0}").format(", ".join(unavailable)),
				indicator="orange",
				alert=True,
			)

	def calculate_totals(self):
		for item in self.items:
			item.amount = flt(item.qty) * flt(item.rate)
		self.total_amount = sum(flt(item.amount) for item in self.items)

	def set_partnership_and_commission(self):
		partnership = get_active_partnership(self.distributor, self.hotel, self.transaction_date)
		self.partnership = partnership.name if partnership else None
		if partnership:
			self.commission_type = partnership.commission_type
			rate, fixed = partnership.commission_rate, partnership.commission_amount
		else:
			# Every registered party is a HAT partner: HAT's default rate applies
			self.commission_type = "HAT Default"
			rate, fixed = frappe.db.get_single_value("HAT Settings", "default_commission_rate"), 0
		if self.commission_type == "None":
			self.commission_amount = 0
		elif self.commission_type == "Fixed Amount per Order":
			self.commission_amount = flt(fixed)
		else:
			self.commission_amount = flt(self.total_amount) * flt(rate) / 100

	def validate_rates(self):
		missing = [str(item.idx) for item in self.items if not flt(item.rate)]
		if missing:
			frappe.throw(
				_("Enter a rate for item rows {0} before the request is quoted").format(", ".join(missing))
			)

	def warn_if_outside_coverage(self):
		territory = frappe.db.get_value("Customer", self.hotel, "territory")
		covered = frappe.get_all(
			"HAT Coverage Area",
			filters={"parent": self.distributor, "parenttype": "Supplier"},
			pluck="territory",
		)
		if covered and territory and territory not in covered:
			frappe.msgprint(
				_("{0} does not list {1} in its delivery coverage").format(
					frappe.bold(self.distributor_name or self.distributor), frappe.bold(territory)
				),
				indicator="orange",
				alert=True,
			)
