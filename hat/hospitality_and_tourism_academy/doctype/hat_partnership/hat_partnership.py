# Copyright (c) 2026, HAT and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class HATPartnership(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hat.hospitality_and_tourism_academy.doctype.hat_category.hat_category import HATCategory

		categories: DF.TableMultiSelect[HATCategory]
		commission_amount: DF.Currency
		commission_rate: DF.Percent
		commission_type: DF.Literal["Percentage", "Fixed Amount per Order", "None"]
		discount_percentage: DF.Percent
		distributor: DF.Link
		distributor_name: DF.Data | None
		end_date: DF.Date | None
		hotel: DF.Link
		hotel_name: DF.Data | None
		payment_terms_template: DF.Link | None
		start_date: DF.Date
		status: DF.Literal["Draft", "Proposed", "Active", "Suspended", "Rejected", "Terminated"]
		terms: DF.TextEditor | None
	# end: auto-generated types

	_DOCTYPE_NAME = "HAT Partnership"

	def validate(self):
		validate_party_group("Customer", self.hotel, "Hotel")
		validate_party_group("Supplier", self.distributor, "Distributor")
		if self.end_date and getdate(self.end_date) < getdate(self.start_date):
			frappe.throw(_("End Date cannot be before Start Date"))
		if self.status == "Active":
			self.validate_no_other_active()

	def validate_no_other_active(self):
		other = frappe.db.exists(
			"HAT Partnership",
			{
				"distributor": self.distributor,
				"hotel": self.hotel,
				"status": "Active",
				"name": ("!=", self.name),
			},
		)
		if other:
			frappe.throw(
				_("{0} is already an active partnership between this distributor and hotel").format(
					frappe.bold(other)
				)
			)


def validate_party_group(doctype, name, group):
	group_field = "customer_group" if doctype == "Customer" else "supplier_group"
	if frappe.db.get_value(doctype, name, group_field) != group:
		frappe.throw(
			_("{0} {1} must be in the {2} group").format(_(doctype), frappe.bold(name), frappe.bold(group))
		)


def get_active_partnership(distributor, hotel, on_date):
	"""The partnership in force between a distributor and a hotel on a date, if any."""
	on_date = getdate(on_date)
	for p in frappe.get_all(
		"HAT Partnership",
		filters={"distributor": distributor, "hotel": hotel, "status": "Active"},
		fields=["name", "start_date", "end_date", "commission_type", "commission_rate", "commission_amount"],
	):
		if getdate(p.start_date) <= on_date and (not p.end_date or getdate(p.end_date) >= on_date):
			return p
