# Copyright (c) 2026, HAT and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class HATListingPriceTier(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from_qty: DF.Float
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		price: DF.Currency
	# end: auto-generated types

	_DOCTYPE_NAME = "HAT Listing Price Tier"
