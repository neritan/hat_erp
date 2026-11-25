# Copyright (c) 2026, HAT and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from hat.notifications import review_saved


class HATDistributorRating(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		comment: DF.SmallText | None
		communication: DF.Rating
		delivery: DF.Rating
		distributor: DF.Link
		distributor_name: DF.Data | None
		hotel: DF.Link
		order_request: DF.Link | None
		quality: DF.Rating
		rating: DF.Rating
		review_type: DF.Literal["Order", "Overall"]
	# end: auto-generated types

	_DOCTYPE_NAME = "HAT Distributor Rating"

	def validate(self):
		self.review_type = "Order" if self.order_request else "Overall"
		if self.order_request:
			self.validate_order_request()
		else:
			self.validate_one_overall_review()

	def validate_one_overall_review(self):
		"""A hotel reviews a distributor overall once; it edits that review rather than adding more."""
		existing = frappe.db.get_value(
			"HAT Distributor Rating",
			{
				"hotel": self.hotel,
				"distributor": self.distributor,
				"order_request": ("is", "not set"),
				"name": ("!=", self.name),
			},
		)
		if existing:
			frappe.throw(
				_("{0} has already reviewed {1}: edit review {2} instead").format(
					frappe.bold(self.hotel), frappe.bold(self.distributor_name or self.distributor), existing
				),
				title=_("Already reviewed"),
			)

	def validate_order_request(self):
		order = frappe.db.get_value(
			"HAT Order Request", self.order_request, ["hotel", "distributor", "status"], as_dict=True
		)
		if (order.hotel, order.distributor) != (self.hotel, self.distributor):
			frappe.throw(
				_("Order Request {0} is not between this hotel and distributor").format(self.order_request)
			)
		if order.status != "Completed":
			frappe.throw(_("Only completed order requests can be rated"))
		if frappe.db.exists(
			"HAT Distributor Rating", {"order_request": self.order_request, "name": ("!=", self.name)}
		):
			frappe.throw(_("Order Request {0} has already been rated").format(self.order_request))

	def on_update(self):
		update_distributor_rating(self.distributor)
		review_saved(self)
		if self.has_value_changed("distributor") and self.get_doc_before_save():
			update_distributor_rating(self.get_doc_before_save().distributor)

	def on_trash(self):
		update_distributor_rating(self.distributor, exclude=self.name)


def update_distributor_rating(distributor, exclude=None):
	filters = {"distributor": distributor}
	if exclude:
		filters["name"] = ("!=", exclude)
	ratings = frappe.get_all("HAT Distributor Rating", filters=filters, pluck="rating")
	average = sum(ratings) / len(ratings) if ratings else 0
	frappe.db.set_value(
		"Supplier",
		distributor,
		{"hat_average_rating": average, "hat_rating_count": len(ratings)},
	)
	frappe.db.set_value("HAT Listing", {"distributor": distributor}, "distributor_rating", average)
