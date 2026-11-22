"""Hotels rating distributors: one rating for each completed order, and one overall review.

Both are HAT Distributor Ratings; the order rating names its order request, the overall review does
not. The distributor's average (shown on listings, the product page and the distributor page) is
taken over all of them. Distributors can read their ratings but not write them.
"""

import frappe
from frappe import _

from hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing import resolve_hotel

RATING_FIELDS = ("rating", "quality", "delivery", "communication", "comment")


@frappe.whitelist()
def get_review(distributor: str, order_request: str | None = None, hotel: str | None = None) -> dict:
	"""The hotel's review to edit: the order's rating, or the overall review when no order is given."""
	hotel = resolve_hotel(hotel)
	if not hotel:
		frappe.throw(_("Only a hotel can review a distributor"), frappe.PermissionError)
	distributor = get_distributor(distributor, order_request, hotel)
	name = frappe.db.get_value("HAT Distributor Rating", review_filters(hotel, distributor, order_request))
	review = {"hotel": hotel, "distributor": distributor, "order_request": order_request, "name": name}
	if name:
		review.update(frappe.db.get_value("HAT Distributor Rating", name, RATING_FIELDS, as_dict=True))
	review["distributor_name"] = frappe.db.get_value("Supplier", distributor, "supplier_name")
	return review


@frappe.whitelist()
def save_review(
	distributor: str,
	rating: float,
	quality: float | None = None,
	delivery: float | None = None,
	communication: float | None = None,
	comment: str | None = None,
	order_request: str | None = None,
	hotel: str | None = None,
) -> str:
	"""Create or update the hotel's review; returns its name. Permissions and rules apply as in the form."""
	hotel = resolve_hotel(hotel)
	if not hotel:
		frappe.throw(_("Only a hotel can review a distributor"), frappe.PermissionError)
	distributor = get_distributor(distributor, order_request, hotel)
	if not rating:
		frappe.throw(_("Give at least one star"))

	name = frappe.db.get_value("HAT Distributor Rating", review_filters(hotel, distributor, order_request))
	doc = (
		frappe.get_doc("HAT Distributor Rating", name)
		if name
		else frappe.new_doc("HAT Distributor Rating").update(
			{"hotel": hotel, "distributor": distributor, "order_request": order_request}
		)
	)
	doc.update(
		{
			"rating": rating,
			"quality": quality or 0,
			"delivery": delivery or 0,
			"communication": communication or 0,
			"comment": comment,
		}
	)
	doc.save()
	return doc.name


def get_distributor(distributor, order_request, hotel):
	"""An order rating is about that order's distributor, whatever the client sent."""
	if not order_request:
		return distributor
	order = frappe.db.get_value("HAT Order Request", order_request, ["hotel", "distributor"], as_dict=True)
	if not order or order.hotel != hotel:
		frappe.throw(
			_("Order Request {0} is not one of your hotel's").format(order_request), frappe.PermissionError
		)
	return order.distributor


def review_filters(hotel, distributor, order_request):
	filters = {"hotel": hotel, "distributor": distributor}
	filters["order_request"] = order_request or ("is", "not set")
	return filters
