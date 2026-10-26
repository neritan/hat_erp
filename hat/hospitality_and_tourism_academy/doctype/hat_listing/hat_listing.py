# Copyright (c) 2026, HAT and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today
from frappe.utils.nestedset import get_ancestors_of

from hat.hospitality_and_tourism_academy.doctype.hat_partnership.hat_partnership import (
	get_active_partnership,
	validate_party_group,
)
from hat.setup.catalogue import CATEGORY_CODES

MARKETPLACE_CURRENCY = "ALL"
STAFF_ROLES = {"HAT Staff", "System Manager", "Administrator"}


class HATListing(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		availability: DF.Literal["Available", "Out of Stock"]
		currency: DF.Link | None
		description: DF.TextEditor | None
		distributor: DF.Link
		distributor_name: DF.Data | None
		distributor_rating: DF.Rating
		image: DF.AttachImage | None
		item: DF.Link
		item_group: DF.Link
		item_name: DF.Data | None
		lead_time_days: DF.Int
		minimum_qty: DF.Float
		price: DF.Currency
		price_type: DF.Literal["Fixed Price", "Price on Request"]
		published: DF.Check
		title: DF.Data
		uom: DF.Link
	# end: auto-generated types

	_DOCTYPE_NAME = "HAT Listing"

	def validate(self):
		validate_party_group("Supplier", self.distributor, "Distributor")
		self.validate_one_offer_per_product()
		if frappe.db.get_value("Item Group", self.item_group, "is_group"):
			frappe.throw(
				_("{0} is a category; choose one of its product groups").format(frappe.bold(self.item_group))
			)
		if self.price_type == "Price on Request":
			self.price = 0
		elif flt(self.price) <= 0:
			frappe.throw(_("Enter a price, or set Price Type to Price on Request"))
		if flt(self.minimum_qty) <= 0:
			self.minimum_qty = 1
		self.currency = MARKETPLACE_CURRENCY
		if self.published and not frappe.db.get_value("Supplier", self.distributor, "hat_verified"):
			frappe.throw(
				_(
					"Only distributors verified by HAT can publish listings. Untick Published to save it, and ask HAT to verify {0}."
				).format(frappe.bold(self.distributor_name or self.distributor))
			)

	def validate_one_offer_per_product(self):
		other = frappe.db.exists(
			"HAT Listing", {"distributor": self.distributor, "item": self.item, "name": ("!=", self.name)}
		)
		if other:
			frappe.throw(
				_("{0} already offers {1} in listing {2}").format(
					frappe.bold(self.distributor_name or self.distributor), frappe.bold(self.item_name), other
				)
			)


def get_listing_rate(listing, hotel, on_date=None):
	"""Price per unit for this hotel: the public price less any partnership discount.

	None for listings priced on request."""
	if listing.price_type == "Price on Request":
		return None
	partnership = hotel and get_active_partnership(listing.distributor, hotel, on_date or today())
	if partnership and partnership_covers(partnership.name, listing.item_group):
		return flt(listing.price) * (100 - flt(partnership.discount_percentage)) / 100
	return flt(listing.price)


def partnership_covers(partnership, item_group):
	"""A partnership without categories covers everything; otherwise the group or a parent must be listed."""
	categories = frappe.get_all(
		"HAT Category",
		filters={"parent": partnership, "parenttype": "HAT Partnership"},
		pluck="item_group",
	)
	if not categories:
		return True
	return bool({item_group, *get_ancestors_of("Item Group", item_group)} & set(categories))


def get_user_hotel(user=None):
	"""The hotel a hotel user belongs to, from their User Permission on Customer."""
	customers = frappe.get_all(
		"User Permission",
		filters={"user": user or frappe.session.user, "allow": "Customer"},
		pluck="for_value",
	)
	hotels = [c for c in customers if frappe.db.get_value("Customer", c, "customer_group") == "Hotel"]
	return hotels[0] if len(hotels) == 1 else None


def resolve_hotel(hotel=None):
	"""The hotel to act for: the user's own, or — for HAT staff only — the one they name.

	Never trust a hotel passed from the client: prices, partner discounts and carts are private."""
	own = get_user_hotel()
	if not hotel or hotel == own:
		return own
	if not set(frappe.get_roles()) & STAFF_ROLES or not frappe.has_permission("Customer", "read", hotel):
		frappe.throw(_("You can only act for your own hotel"), frappe.PermissionError)
	if frappe.db.get_value("Customer", hotel, "customer_group") != "Hotel":
		frappe.throw(_("{0} is not a hotel").format(frappe.bold(hotel)))
	return hotel


@frappe.whitelist()
def get_price_for_hotel(listing: str, hotel: str | None = None) -> dict:
	doc = frappe.get_doc("HAT Listing", listing)
	doc.check_permission("read")
	hotel = resolve_hotel(hotel)
	return {"hotel": hotel, "rate": get_listing_rate(doc, hotel), "public_price": doc.price}


@frappe.whitelist()
def get_distributors_for_region(hotel: str | None = None) -> list[str]:
	"""Distributors that list the hotel's territory in their coverage, or list no coverage at all."""
	hotel = resolve_hotel(hotel)
	territory = hotel and frappe.db.get_value("Customer", hotel, "territory")
	if not territory:
		frappe.throw(_("Set the hotel's Territory to filter by delivery region"))
	coverage = {}
	for row in frappe.get_all(
		"HAT Coverage Area", filters={"parenttype": "Supplier"}, fields=["parent", "territory"]
	):
		coverage.setdefault(row.parent, set()).add(row.territory)
	return [
		d
		for d in frappe.get_all("Supplier", filters={"supplier_group": "Distributor"}, pluck="name")
		if d not in coverage or territory in coverage[d]
	]


@frappe.whitelist(methods=["POST"])
def create_product(item_name: str, item_group: str, uom: str) -> str:
	"""Add a product to the HAT catalogue for a new listing, or return the one with the same name."""
	if not frappe.has_permission("HAT Listing", "create"):
		frappe.throw(_("Not permitted to create products"), frappe.PermissionError)
	item_name = item_name.strip()
	existing = frappe.db.get_value("Item", {"item_name": item_name, "disabled": 0})
	if existing:
		return existing
	if frappe.db.get_value("Item Group", item_group, "is_group"):
		frappe.throw(_("{0} is a category; choose one of its product groups").format(frappe.bold(item_group)))
	distributors = frappe.get_all(
		"User Permission", filters={"user": frappe.session.user, "allow": "Supplier"}, pluck="for_value"
	)
	return (
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": next_item_code(item_group),
				"item_name": item_name[:140],
				"description": item_name,
				"item_group": item_group,
				"stock_uom": uom,
				"is_stock_item": 0,
				"is_purchase_item": 1,
				"is_sales_item": 1,
				"include_item_in_manufacturing": 0,
				"supplier_items": [{"supplier": d} for d in distributors],
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def next_item_code(item_group):
	"""HAT-<category code>-0001, numbered per top-level category."""
	groups = {item_group, *get_ancestors_of("Item Group", item_group)}
	code = next((code for category, code in CATEGORY_CODES.items() if category in groups), "GN")
	prefix = f"HAT-{code}-"
	numbers = [
		int(name.removeprefix(prefix))
		for name in frappe.get_all("Item", filters={"name": ("like", f"{prefix}%")}, pluck="name")
		if name.removeprefix(prefix).isdigit()
	]
	return f"{prefix}{max(numbers, default=0) + 1:04d}"


OFFER_FIELDS = [
	"name",
	"item",
	"title",
	"item_group",
	"distributor",
	"distributor_name",
	"distributor_rating",
	"price_type",
	"price",
	"uom",
	"minimum_qty",
	"lead_time_days",
	"availability",
]


@frappe.whitelist()
def get_marketplace(
	search: str | None = None,
	item_group: str | None = None,
	hotel: str | None = None,
	in_my_region: bool = False,
	available_only: bool = False,
	start: int = 0,
	page_length: int = 24,
) -> dict:
	"""Products on the marketplace, each with the offers of every distributor that sells it."""
	hotel = resolve_hotel(hotel)
	filters = [["published", "=", 1]]
	if item_group:
		filters.append(["item_group", "descendants of (inclusive)", item_group])
	if frappe.utils.sbool(available_only):
		filters.append(["availability", "=", "Available"])
	if frappe.utils.sbool(in_my_region):
		filters.append(["distributor", "in", get_distributors_for_region(hotel) or [""]])
	or_filters = None
	if search:
		or_filters = [[field, "like", f"%{search}%"] for field in ("item_name", "title", "distributor_name")]

	products = frappe.get_list(
		"HAT Listing",
		filters=filters,
		or_filters=or_filters,
		fields=["item", "item_name"],
		distinct=True,
		order_by="item_name asc",
		start=frappe.utils.cint(start),
		page_length=frappe.utils.cint(page_length) + 1,
	)
	has_more = len(products) > frappe.utils.cint(page_length)
	codes = [p.item for p in products[: frappe.utils.cint(page_length)]]
	if not codes:
		return {"hotel": hotel, "products": [], "has_more": False}

	offers = {}
	for offer in frappe.get_list(
		"HAT Listing", filters=[*filters, ["item", "in", codes]], fields=OFFER_FIELDS, limit_page_length=0
	):
		offer.rate = get_listing_rate(offer, hotel)
		offers.setdefault(offer.item, []).append(offer)
	items = {
		item.name: item
		for item in frappe.get_all(
			"Item", filters={"name": ("in", codes)}, fields=["name", "item_name", "item_group", "image"]
		)
	}
	result = []
	for code in codes:
		product_offers = sorted(
			offers.get(code, []),
			key=lambda o: (o.availability != "Available", o.rate is None, o.rate or 0),
		)
		fixed = [o.rate for o in product_offers if o.availability == "Available" and o.rate is not None]
		for offer in product_offers:
			offer.best_price = len(fixed) > 1 and offer.rate == min(fixed)
		result.append({**items[code], "offers": product_offers})
	return {"hotel": hotel, "products": result, "has_more": has_more}


@frappe.whitelist(methods=["POST"])
def add_to_order(listing: str, qty: float, hotel: str | None = None) -> str:
	"""Add a listing to the hotel's draft order request with its distributor, creating it if needed."""
	doc = frappe.get_doc("HAT Listing", listing)
	doc.check_permission("read")
	if not doc.published:
		frappe.throw(_("{0} is not published").format(frappe.bold(doc.title)))
	if doc.availability != "Available":
		frappe.throw(_("{0} is out of stock").format(frappe.bold(doc.title)))
	hotel = resolve_hotel(hotel)
	if not hotel:
		frappe.throw(_("Select the hotel you are ordering for"))

	draft = frappe.get_list(
		"HAT Order Request",
		filters={"hotel": hotel, "distributor": doc.distributor, "status": "Draft"},
		pluck="name",
		order_by="creation desc",
		limit=1,
	)
	if draft:
		order = frappe.get_doc("HAT Order Request", draft[0])
	else:
		order = frappe.new_doc("HAT Order Request")
		order.update({"hotel": hotel, "distributor": doc.distributor})

	order.append(
		"items",
		{
			"listing": doc.name,
			"item_group": doc.item_group,
			"item": doc.item,
			"description": doc.title,
			"qty": flt(qty),
			"uom": doc.uom,
			"rate": get_listing_rate(doc, hotel, order.transaction_date),
		},
	)
	order.save()
	return order.name


def is_hotel_only(user):
	roles = set(frappe.get_roles(user))
	return "Hotel" in roles and not roles & STAFF_ROLES


def get_permission_query_conditions(user=None):
	"""Hotels only see published listings of verified distributors."""
	user = user or frappe.session.user
	if not is_hotel_only(user):
		return ""
	return (
		"`tabHAT Listing`.published = 1 and `tabHAT Listing`.distributor in "
		"(select name from `tabSupplier` where hat_verified = 1)"
	)


def has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if not is_hotel_only(user):
		return True
	return bool(doc.published and frappe.db.get_value("Supplier", doc.distributor, "hat_verified"))


def get_item_dashboard(data):
	"""Show the distributors' listings of a product on the Item form."""
	data.setdefault("non_standard_fieldnames", {})["HAT Listing"] = "item"
	data.setdefault("transactions", []).insert(0, {"label": _("HAT Marketplace"), "items": ["HAT Listing"]})
	return data
