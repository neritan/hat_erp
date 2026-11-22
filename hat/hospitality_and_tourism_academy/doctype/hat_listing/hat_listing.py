# Copyright (c) 2026, HAT and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today
from frappe.utils.html_utils import sanitize_html
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

		from hat.hospitality_and_tourism_academy.doctype.hat_listing_price_tier.hat_listing_price_tier import (
			HATListingPriceTier,
		)

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
		price_tiers: DF.Table[HATListingPriceTier]
		price_type: DF.Literal["Fixed Price", "Price on Request", "Price on Quantity"]
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
		if self.price_type == "Price on Quantity":
			self.validate_price_tiers()
		else:
			self.price_tiers = []
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
					"Only distributors verified by Hatix can publish listings. Untick Published to save it, and ask Hatix to verify {0}."
				).format(frappe.bold(self.distributor_name or self.distributor))
			)

	def validate_price_tiers(self):
		"""Sort the ranges; the first one sets the listed price and the minimum order."""
		if not self.price_tiers:
			frappe.throw(_("Add at least one quantity range with its price"))
		self.price_tiers.sort(key=lambda row: flt(row.from_qty))
		seen = set()
		for idx, row in enumerate(self.price_tiers, start=1):
			row.idx = idx
			if flt(row.from_qty) <= 0:
				frappe.throw(_("Price by Quantity row {0}: From Quantity must be more than 0").format(idx))
			if flt(row.price) <= 0:
				frappe.throw(_("Price by Quantity row {0}: enter a price per unit").format(idx))
			if flt(row.from_qty) in seen:
				frappe.throw(
					_("Price by Quantity: two rows start at quantity {0}").format(frappe.bold(row.from_qty))
				)
			seen.add(flt(row.from_qty))
		self.price = self.price_tiers[0].price
		self.minimum_qty = self.price_tiers[0].from_qty

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


def get_listing_rate(listing, hotel, on_date=None, qty=None):
	"""Price per unit for this hotel: the public price less any partnership discount.

	With Price on Quantity the public price is the one of the range `qty` falls in (the first
	range when no quantity is given). None for listings priced on request."""
	if listing.price_type == "Price on Request":
		return None
	price = flt(listing.price)
	if listing.price_type == "Price on Quantity" and qty is not None:
		price = tier_price(get_price_tiers(listing), qty) or price
	return price * (100 - get_partner_discount(listing, hotel, on_date)) / 100


def get_partner_discount(listing, hotel, on_date=None):
	"""The hotel's partnership discount % with this distributor, if it covers the listing's category."""
	partnership = hotel and get_active_partnership(listing.distributor, hotel, on_date or today())
	if partnership and partnership_covers(partnership.name, listing.item_group):
		return flt(partnership.discount_percentage)
	return 0


def get_price_tiers(listing):
	"""[(from_qty, price), ...] sorted by quantity, from a listing doc or a listing name/dict."""
	rows = listing.get("price_tiers") if isinstance(listing, Document) else None
	if rows is None:
		rows = frappe.get_all(
			"HAT Listing Price Tier",
			filters={"parent": listing.name, "parenttype": "HAT Listing", "parentfield": "price_tiers"},
			fields=["from_qty", "price"],
		)
	return sorted((flt(row.from_qty), flt(row.price)) for row in rows)


def tier_price(tiers, qty):
	"""Price of the range `qty` falls in: the last range starting at or below it (whole quantity)."""
	price = None
	for from_qty, tier in tiers:
		if flt(qty) >= from_qty:
			price = tier
	return price if price is not None else (tiers[0][1] if tiers else None)


def get_tier_rates(listing, hotel, on_date=None):
	"""The ranges as the hotel sees them: public price and the hotel's price per range."""
	if listing.price_type != "Price on Quantity":
		return []
	discount = get_partner_discount(listing, hotel, on_date)
	return [
		{"from_qty": from_qty, "price": price, "rate": price * (100 - discount) / 100}
		for from_qty, price in get_price_tiers(listing)
	]


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
	return {
		"hotel": hotel,
		"rate": get_listing_rate(doc, hotel),
		"public_price": doc.price,
		"price_type": doc.price_type,
		"tiers": get_tier_rates(doc, hotel),
	}


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
	distributor: str | None = None,
) -> dict:
	"""Products on the marketplace, each with the offers of every distributor that sells it.

	`search` matches the product only (name or code); `distributor` keeps that distributor's offers."""
	hotel = resolve_hotel(hotel)
	filters = [["published", "=", 1]]
	if distributor:
		filters.append(["distributor", "=", distributor])
	if item_group:
		filters.append(["item_group", "descendants of (inclusive)", item_group])
	if frappe.utils.sbool(available_only):
		filters.append(["availability", "=", "Available"])
	if frappe.utils.sbool(in_my_region):
		filters.append(["distributor", "in", get_distributors_for_region(hotel) or [""]])
	or_filters = None
	if search:
		or_filters = [[field, "like", f"%{search}%"] for field in ("item_name", "item")]

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

	offers = get_offers(codes, filters, hotel)
	items = {
		item.name: item
		for item in frappe.get_all(
			"Item", filters={"name": ("in", codes)}, fields=["name", "item_name", "item_group", "image"]
		)
	}
	result = [{**items[code], "offers": offers.get(code, [])} for code in codes]
	return {"hotel": hotel, "products": result, "has_more": has_more}


def get_offers(codes, filters, hotel):
	"""The offers the user may see for these products, priced for the hotel: {item: [offer, ...]}.

	Each product's offers come available first, then cheapest; `best_price` marks the cheapest
	fixed price when several distributors compete."""
	offers = {}
	for offer in frappe.get_list(
		"HAT Listing", filters=[*filters, ["item", "in", codes]], fields=OFFER_FIELDS, limit_page_length=0
	):
		offer.rate = get_listing_rate(offer, hotel)
		offer.tiers = get_tier_rates(offer, hotel)
		offers.setdefault(offer.item, []).append(offer)
	for product_offers in offers.values():
		product_offers.sort(key=lambda o: (o.availability != "Available", o.rate is None, o.rate or 0))
		fixed = [o.rate for o in product_offers if o.availability == "Available" and o.rate is not None]
		for offer in product_offers:
			offer.best_price = len(fixed) > 1 and offer.rate == min(fixed)
	return offers


RELATED_PRODUCTS = 6


@frappe.whitelist()
def get_product(item: str, hotel: str | None = None) -> dict:
	"""Everything a hotel needs to choose a product: details, every distributor's offer, those
	distributors, and other products of the same category.

	Only products with a published listing the user may see are shown, so the page never reveals
	an item that is not on the marketplace."""
	hotel = resolve_hotel(hotel)
	filters = [["published", "=", 1]]
	offers = get_offers([item], filters, hotel).get(item)
	if not offers:
		frappe.throw(_("This product is not on the marketplace"), frappe.DoesNotExistError)

	product = frappe.get_all(
		"Item",
		filters={"name": item},
		fields=["name", "item_name", "item_group", "image", "description", "stock_uom"],
	)[0]
	# The description is a Text Editor field; clean it before the page renders it as HTML.
	product.description = sanitize_html(product.description or "")
	return {
		"hotel": hotel,
		"product": product,
		"offers": offers,
		"distributors": get_distributor_cards([o.distributor for o in offers], hotel),
		"related": get_related_products(product, filters, hotel),
	}


def get_distributor_cards(distributors, hotel):
	"""What a hotel wants to know about each distributor before ordering."""
	names = list(dict.fromkeys(distributors))
	territory = hotel and frappe.db.get_value("Customer", hotel, "territory")
	coverage = {}
	for row in frappe.get_all(
		"HAT Coverage Area",
		filters={"parenttype": "Supplier", "parent": ("in", names)},
		fields=["parent", "territory"],
		order_by="idx asc",
	):
		coverage.setdefault(row.parent, []).append(row.territory)
	suppliers = {
		s.name: s
		for s in frappe.get_all(
			"Supplier",
			filters={"name": ("in", names)},
			fields=[
				"name",
				"supplier_name",
				"hat_verified",
				"hat_average_rating",
				"hat_minimum_order",
				"email_id",
				"mobile_no",
				"website",
			],
		)
	}
	cards = []
	for name in names:
		card = suppliers[name]
		card.coverage = coverage.get(name, [])
		# No coverage listed means the distributor delivers everywhere, as in the region filter.
		card.delivers_to_hotel = (not card.coverage or territory in card.coverage) if territory else None
		cards.append(card)
	return cards


def get_related_products(product, filters, hotel):
	"""Other products of the same category on the marketplace, with their lowest price."""
	codes = [
		row.item
		for row in frappe.get_list(
			"HAT Listing",
			filters=[*filters, ["item_group", "=", product.item_group], ["item", "!=", product.name]],
			fields=["item", "item_name"],
			distinct=True,
			order_by="item_name asc",
			page_length=RELATED_PRODUCTS,
		)
	]
	if not codes:
		return []
	offers = get_offers(codes, filters, hotel)
	items = frappe.get_all(
		"Item", filters={"name": ("in", codes)}, fields=["name", "item_name", "item_group", "image"]
	)
	related = []
	for item in sorted(items, key=lambda i: i.item_name):
		item_offers = offers.get(item.name, [])
		rates = [
			rate
			for o in item_offers
			if o.availability == "Available" and o.rate is not None
			for rate in ([t["rate"] for t in o.tiers] if o.tiers else [o.rate])
		]
		item.lowest_rate = min(rates) if rates else None
		item.offer_count = len(item_offers)
		related.append(item)
	return related


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
			"rate": get_listing_rate(doc, hotel, order.transaction_date, flt(qty)),
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
	data.setdefault("transactions", []).insert(0, {"label": _("Hatix Marketplace"), "items": ["HAT Listing"]})
	return data


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def verified_distributor_query(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: dict | None = None
) -> list:
	"""Link search for verified distributors, the ones the marketplace shows.

	Hotels may not read Supplier.hat_verified (only HAT staff set it), so they cannot filter on it
	from the browser; whether a distributor is verified is public, so the filter is applied here."""
	if not frappe.has_permission("Supplier", "read"):
		return []
	txt = f"%{txt or ''}%"
	return frappe.get_all(
		"Supplier",
		filters={"supplier_group": "Distributor", "hat_verified": 1, "disabled": 0},
		or_filters=[["name", "like", txt], ["supplier_name", "like", txt]],
		fields=["name", "supplier_name"],
		order_by="supplier_name asc",
		limit_start=start,
		limit_page_length=page_len,
		as_list=True,
	)
