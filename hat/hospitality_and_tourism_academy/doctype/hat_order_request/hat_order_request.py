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
		self.calculate_totals()
		self.set_partnership_and_commission()
		if self.status in ("Quoted", "Accepted", "Delivered", "Completed"):
			self.validate_rates()
		if self.is_new() or self.has_value_changed("distributor") or self.has_value_changed("hotel"):
			self.warn_if_outside_coverage()

	def calculate_totals(self):
		for item in self.items:
			item.amount = flt(item.qty) * flt(item.rate)
		self.total_amount = sum(flt(item.amount) for item in self.items)

	def set_partnership_and_commission(self):
		partnership = get_active_partnership(self.distributor, self.hotel, self.transaction_date)
		self.partnership = partnership.name if partnership else None
		self.commission_type = partnership.commission_type if partnership else None
		if not partnership or partnership.commission_type == "None":
			self.commission_amount = 0
		elif partnership.commission_type == "Percentage":
			self.commission_amount = flt(self.total_amount) * flt(partnership.commission_rate) / 100
		else:
			self.commission_amount = flt(partnership.commission_amount)

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
