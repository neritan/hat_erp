"""In-app notifications between hotels and distributors.

Each notification is a Notification Log for every enabled user of the hotel or distributor
concerned (found through their User Permission), except the user who caused it. Frappe shows it in
the bell, and also emails it once the site has an outgoing email account.

What sends what:
- HAT Order Request: a new order to the distributor; every later status change to both sides.
- HAT Distributor Rating: a new or changed review to the distributor.
- HAT Quote Request / HAT Quote: a published request to matching distributors, a submitted quote
  to the hotel, awarded / not selected to each distributor that quoted (see those doctypes).
"""

import frappe
from frappe import _


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


def order_status_changed(doc):
	"""HAT Order Request on_update: tell the distributor about a new order, and both sides about
	every later change. A draft is the hotel's cart, so nobody hears about it until it is sent."""
	before = doc.get_doc_before_save()
	old = before.status if before else None
	if doc.status == old or doc.status == "Draft" or (old in (None, "Draft") and doc.status == "Cancelled"):
		return

	labels = {
		"order": frappe.bold(doc.name),
		"hotel": doc.hotel_name or doc.hotel,
		"distributor": doc.distributor_name or doc.distributor,
	}
	if doc.status == "Sent":
		subject = (
			_("New request for quotation {order} from {hotel}")
			if doc.request_type == "Request for Quotation"
			else _("New order {order} from {hotel}")
		)
		notify(users_of("Supplier", [doc.distributor]), doc, subject.format(**labels))
		return

	# What both sides read when the order reaches each status
	subject = {
		"Quoted": _("{distributor} sent a quote for {order}"),
		"Accepted": _("{order} was accepted"),
		"Delivered": _("{distributor} delivered {order}"),
		"Completed": _("{hotel} confirmed receipt of {order}"),
		"Rejected": _("{order} was declined"),
		"Cancelled": _("{hotel} cancelled {order}"),
	}.get(doc.status, _("{order} is now {status}"))
	notify(
		users_of("Customer", [doc.hotel]) + users_of("Supplier", [doc.distributor]),
		doc,
		subject.format(status=_(doc.status), **labels),
	)


def review_saved(doc):
	"""HAT Distributor Rating on_update: tell the distributor about a new or changed review."""
	before = doc.get_doc_before_save()
	if before and not any(doc.has_value_changed(f) for f in ("rating", "comment")):
		return
	labels = {
		"hotel": frappe.db.get_value("Customer", doc.hotel, "customer_name") or doc.hotel,
		"stars": round((doc.rating or 0) * 5),
		"order": doc.order_request,
	}
	if before:
		subject = _("{hotel} updated its review: {stars}/5")
	elif doc.order_request:
		subject = _("{hotel} rated order {order}: {stars}/5")
	else:
		subject = _("New review from {hotel}: {stars}/5")
	notify(users_of("Supplier", [doc.distributor]), doc, subject.format(**labels))
