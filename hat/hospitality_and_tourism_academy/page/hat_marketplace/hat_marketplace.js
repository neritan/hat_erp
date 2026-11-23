// Products on the HAT marketplace, each with the offers of every distributor that sells it

frappe.pages["hat-marketplace"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Marketplace"),
		single_column: true,
	});
	wrapper.marketplace = new HATMarketplace(page);
};

frappe.pages["hat-marketplace"].on_page_show = (wrapper) => {
	// e.g. "All products from this distributor" on a product page
	if (frappe.route_options?.distributor) {
		const { distributor } = frappe.route_options;
		frappe.route_options = null;
		wrapper.marketplace.distributor.set_value(distributor);
		wrapper.marketplace.update_cart_count();
		return; // setting the filter refreshes the list
	}
	wrapper.marketplace.refresh();
	wrapper.marketplace.update_cart_count();
};

const MARKETPLACE_API = "hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing";
const is_staff = () => frappe.user.has_role("HAT Staff") || frappe.user.has_role("System Manager");

// How products are laid out; the choice is remembered per browser
const VIEWS = ["grid", "supplier", "compact"];
const VIEW_KEY = "hat-marketplace-view";
const product_url = (code) => `/desk/hat-product/${encodeURIComponent(code)}`;
const saved_view = () => {
	try {
		const view = localStorage.getItem(VIEW_KEY);
		return VIEWS.includes(view) ? view : "grid";
	} catch {
		return "grid";
	}
};

class HATMarketplace {
	constructor(page) {
		this.page = page;
		this.page_length = 24;
		this.offers = {};
		this.products = {};
		this.product_list = [];
		this.make_filters();
		this.$body = $(`
			<div class="hat-marketplace">
				<div class="hat-mp-summary text-muted small"></div>
				<div class="hat-mp-grid"></div>
				<div class="hat-mp-more"></div>
			</div>`).appendTo(page.main);
		this.$grid = this.$body.find(".hat-mp-grid");
		this.$more = this.$body.find(".hat-mp-more");
		this.$summary = this.$body.find(".hat-mp-summary");
		this.$grid.on("click", "[data-add-listing]", (e) => {
			const offer = this.offers[$(e.currentTarget).attr("data-add-listing")];
			// the compact list has its own quantity box next to the button
			const qty = flt($(e.currentTarget).closest(".hat-mp-row").find(".hat-mp-qty").val());
			hat.marketplace.add_to_order(offer, this.hotel || undefined, qty || undefined);
		});
		this.$grid.on("click", "[data-step]", (e) => {
			const $qty = $(e.currentTarget).siblings(".hat-mp-qty");
			const min = flt($qty.attr("min")) || 1;
			$qty.val(Math.max(min, flt($qty.val()) + flt($(e.currentTarget).attr("data-step"))));
		});
		this.$grid.on("click", "[data-show-offers]", (e) => {
			e.preventDefault();
			$(e.currentTarget)
				.closest("[data-product]")
				.find(".hat-mp-compare")
				.toggleClass("hidden");
		});
		// clicking a distributor's name filters the marketplace to that distributor
		this.$grid.on("click", "[data-filter-distributor]", (e) => {
			e.preventDefault();
			this.distributor.set_value($(e.currentTarget).attr("data-filter-distributor"));
			window.scrollTo({ top: 0, behavior: "smooth" });
		});
		this.$grid.on("click", "[data-request-quotes]", (e) => {
			const product = this.products[$(e.currentTarget).attr("data-request-quotes")];
			hat.marketplace.request_quotes(product, this.hotel || undefined);
		});
		this.$more.on("click", "button", () => this.refresh(true));
		this.page.set_secondary_action(__("Refresh"), () => this.refresh(), "refresh");
		if (frappe.model.can_create("HAT Order Request")) {
			// namespaced and unbound first, so a re-created page never stacks handlers
			$(document)
				.off("hat:cart-count.hat-marketplace")
				.on("hat:cart-count.hat-marketplace", () => this.update_cart_count());
		}
	}

	async update_cart_count() {
		if (!frappe.model.can_create("HAT Order Request")) return;
		const { message: count } = await frappe.call("hat.cart.get_cart_count", {
			hotel: this.hotel_field?.get_value() || null,
		});
		this.page.set_primary_action(
			count ? __("Cart ({0})", [count]) : __("Cart"),
			() => frappe.set_route("hat-cart"),
			"shopping-cart"
		);
	}

	make_filters() {
		const refresh = frappe.utils.debounce(() => this.refresh(), 300);
		this.view = this.page.add_field({
			fieldname: "view",
			fieldtype: "Select",
			label: __("View"),
			options: [
				{ value: "grid", label: __("Grid") },
				{ value: "supplier", label: __("Supplier cards") },
				{ value: "compact", label: __("Compact list") },
			],
			default: saved_view(),
			change: () => {
				try {
					localStorage.setItem(VIEW_KEY, this.get_view());
				} catch {
					// private window or blocked storage: the choice just isn't remembered
				}
				this.render();
			},
		});
		this.search = this.page.add_field({
			fieldname: "search",
			fieldtype: "Data",
			label: __("Search product"),
			change: refresh,
		});
		this.search.$input.on("input", refresh);
		this.item_group = this.page.add_field({
			fieldname: "item_group",
			fieldtype: "Link",
			options: "Item Group",
			label: __("Category"),
			change: refresh,
		});
		this.distributor = this.page.add_field({
			fieldname: "distributor",
			fieldtype: "Link",
			options: "Supplier",
			label: __("Distributor"),
			// Server-side: hotels may not filter on hat_verified themselves
			get_query: () => ({
				query: "hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing.verified_distributor_query",
			}),
			change: refresh,
		});
		if (is_staff()) {
			this.hotel_field = this.page.add_field({
				fieldname: "hotel",
				fieldtype: "Link",
				options: "Customer",
				label: __("Prices for hotel"),
				get_query: () => ({ filters: { customer_group: "Hotel" } }),
				change: () => {
					refresh();
					this.update_cart_count();
				},
			});
		}
		this.available_only = this.page.add_field({
			fieldname: "available_only",
			fieldtype: "Check",
			label: __("Available only"),
			change: refresh,
		});
		if (frappe.user.has_role("Hotel") || is_staff()) {
			this.in_my_region = this.page.add_field({
				fieldname: "in_my_region",
				fieldtype: "Check",
				label: __("Delivers to my region"),
				change: refresh,
			});
		}
	}

	async refresh(append = false) {
		const start = append ? this.loaded : 0;
		const { message } = await frappe.call({
			method: `${MARKETPLACE_API}.get_marketplace`,
			args: {
				search: this.search.get_value() || null,
				item_group: this.item_group.get_value() || null,
				distributor: this.distributor.get_value() || null,
				hotel: this.hotel_field?.get_value() || null,
				available_only: this.available_only.get_value() ? 1 : 0,
				in_my_region: this.in_my_region?.get_value() ? 1 : 0,
				start,
				page_length: this.page_length,
			},
		});
		this.hotel = message.hotel;
		if (!append) this.product_list = [];
		this.product_list.push(...message.products);
		this.loaded = this.product_list.length;
		this.render();
		// Partnerships are between HAT and distributors: hotels just see their prices
		this.$summary.text(
			hat.profile.is_only("Hotel")
				? __("Prices for {0}.", [this.hotel])
				: this.hotel
				? __("Prices for {0}. Partner prices are shown where you have a partnership.", [
						this.hotel,
				  ])
				: __("Public prices. Choose a hotel to see its partner prices.")
		);
		this.$more.html(
			message.has_more
				? `<button class="btn btn-default btn-sm">${__("Load more products")}</button>`
				: ""
		);
	}

	get_view() {
		const view = this.view.get_value();
		return VIEWS.includes(view) ? view : "grid";
	}

	// Draw the loaded products in the chosen view; switching views needs no new request
	render() {
		const view = this.get_view();
		this.offers = {};
		this.products = {};
		this.$grid.attr("class", `hat-mp-grid hat-mp-view-${view}`);
		if (!this.product_list.length) {
			this.$grid.html(
				`<div class="hat-mp-empty text-muted">${__(
					"No products match these filters."
				)}</div>`
			);
			return;
		}
		const draw = { grid: "grid_html", supplier: "supplier_html", compact: "compact_html" }[
			view
		];
		this.$grid.html(this.product_list.map((product) => this[draw](product)).join(""));
	}

	// The offer a card leads with: offers come sorted available first, then cheapest
	main_offer(product) {
		return product.offers[0];
	}

	image_html(product) {
		const image = product.image
			? `<img src="${encodeURI(product.image)}" alt="" loading="lazy">`
			: `<span>${frappe.utils.escape_html(frappe.get_abbr(product.item_name))}</span>`;
		return `<a class="hat-mp-image-link" href="${product_url(
			product.name
		)}" tabindex="-1">${image}</a>`;
	}

	name_html(product) {
		return `<a class="hat-mp-name" href="${product_url(
			product.name
		)}">${frappe.utils.escape_html(product.item_name)}</a>`;
	}

	// Lowest price a hotel can get for this product, over every offer and quantity range
	lowest_rate(product) {
		const rates = product.offers
			.filter((o) => o.availability === "Available" && o.rate !== null)
			.flatMap((o) => (o.tiers && o.tiers.length ? o.tiers.map((t) => t.rate) : [o.rate]));
		return rates.length ? Math.min(...rates) : null;
	}

	headline_price_html(product, offer) {
		const lowest = this.lowest_rate(product);
		if (lowest === null) {
			return `<div class="hat-mp-big-price text-muted">${__("Price on request")}</div>`;
		}
		const several =
			product.offers.filter((o) => o.rate !== null).length > 1 || (offer.tiers || []).length;
		const from = several ? `<span class="hat-mp-from">${__("from")}</span> ` : "";
		const was =
			!several && offer.rate < offer.price
				? ` <s class="text-muted small">${format_currency(offer.price, "ALL", 0)}</s>`
				: "";
		return `<div class="hat-mp-big-price">${from}${format_currency(
			lowest,
			"ALL",
			0
		)}${was}</div>`;
	}

	terms(offer) {
		return [
			__("per {0}", [__(offer.uom)]),
			__("min. {0}", [offer.minimum_qty]),
			offer.lead_time_days ? __("{0} days", [offer.lead_time_days]) : null,
		]
			.filter(Boolean)
			.join(" · ");
	}

	distributor_html(offer) {
		const esc = frappe.utils.escape_html;
		const rating = offer.distributor_rating
			? `<span class="hat-mp-rating">★ ${(offer.distributor_rating * 5).toFixed(
					1
			  )}</span> · `
			: "";
		return `${rating}<a href="#" data-filter-distributor="${esc(offer.distributor)}"
			title="${esc(__("Show only {0}'s products", [offer.distributor_name]))}">${esc(
			offer.distributor_name
		)}</a>`;
	}

	status_pill(product, offer) {
		if (offer.availability !== "Available") {
			return `<span class="indicator-pill red">${__("Out of stock")}</span>`;
		}
		if (this.lowest_rate(product) === null) {
			return `<span class="indicator-pill blue">${__("On request")}</span>`;
		}
		return `<span class="indicator-pill green">${__("In stock")}</span>`;
	}

	// Add to cart, or Request quote when nobody has a price; "" when the user can do neither
	action_html(product, offer, { small = false, label } = {}) {
		const esc = frappe.utils.escape_html;
		const size = small ? "btn-sm" : "";
		if (offer.availability !== "Available") return "";
		if (offer.rate === null && frappe.model.can_create("HAT Quote Request")) {
			return `<button class="btn btn-default ${size} hat-mp-btn" data-request-quotes="${esc(
				product.name
			)}" title="${__("Ask all distributors of this category for a price")}">${__(
				"Request quote"
			)}</button>`;
		}
		if (hat.marketplace.can_order()) {
			return `<button class="btn btn-primary ${size} hat-mp-btn" data-add-listing="${esc(
				offer.name
			)}">${label || __("Add to cart")}</button>`;
		}
		return "";
	}

	// Every distributor's offer for the product, shown under the card on "Compare offers"
	compare_html(product) {
		if (product.offers.length < 2) return "";
		return `<div class="hat-mp-compare hidden">${product.offers
			.map((offer) => this.offer_html(offer))
			.join("")}</div>`;
	}

	compare_link(product) {
		const count = product.offers.length;
		if (count < 2) return "";
		return `<a href="#" class="hat-mp-compare-link" data-show-offers>${__(
			"Compare {0} offers",
			[count]
		)}</a>`;
	}

	remember(product) {
		this.products[product.name] = product;
		product.offers.forEach((offer) => (this.offers[offer.name] = offer));
	}

	// A: image-first grid
	grid_html(product) {
		const esc = frappe.utils.escape_html;
		const offer = this.main_offer(product);
		this.remember(product);
		return `
			<div class="hat-mp-card hat-mp-tile" data-product="${esc(product.name)}">
				<div class="hat-mp-photo">
					${this.image_html(product)}
					<div class="hat-mp-badge">${this.status_pill(product, offer)}</div>
				</div>
				<div class="hat-mp-body">
					<div class="text-muted small">${esc(product.item_group)}</div>
					${this.name_html(product)}
					<div class="small text-muted">${this.distributor_html(offer)}</div>
					${this.headline_price_html(product, offer)}
					<div class="text-muted small">${esc(this.terms(offer))}</div>
					<div class="hat-mp-actions">
						${this.action_html(product, offer)}
						${this.compare_link(product)}
					</div>
				</div>
				${this.compare_html(product)}
			</div>`;
	}

	// B: B2B supplier card
	supplier_html(product) {
		const esc = frappe.utils.escape_html;
		const offer = this.main_offer(product);
		const count = product.offers.length;
		this.remember(product);
		const details = [
			__("MOQ {0}", [offer.minimum_qty]),
			offer.lead_time_days ? __("lead time {0} days", [offer.lead_time_days]) : null,
		]
			.filter(Boolean)
			.join(" · ");
		return `
			<div class="hat-mp-card hat-mp-wide" data-product="${esc(product.name)}">
				<div class="hat-mp-wide-row">
					<div class="hat-mp-photo">${this.image_html(product)}</div>
					<div class="hat-mp-body">
						${this.name_html(product)}
						<div class="text-muted small">${esc(product.item_group)} · ${esc(__(offer.uom))}</div>
						<div class="hat-mp-pills">
							<span class="indicator-pill green">${__("Verified by Hatix")}</span>
							${count > 1 ? `<span class="indicator-pill blue">${__("{0} distributors", [count])}</span>` : ""}
							${offer.availability !== "Available" ? this.status_pill(product, offer) : ""}
						</div>
						<div class="small text-muted">${this.distributor_html(offer)}</div>
					</div>
					<div class="hat-mp-buy">
						${this.headline_price_html(product, offer)}
						<div class="text-muted small">${esc(details)}</div>
						${this.action_html(product, offer)}
						${this.compare_link(product)}
					</div>
				</div>
				${this.compare_html(product)}
			</div>`;
	}

	// C: compact rows for repeat buying
	compact_html(product) {
		const esc = frappe.utils.escape_html;
		const offer = this.main_offer(product);
		this.remember(product);
		const count = product.offers.length;
		const can_add =
			offer.availability === "Available" &&
			offer.rate !== null &&
			hat.marketplace.can_order();
		const price =
			offer.rate === null
				? `<span class="text-muted">${__("On request")}</span>`
				: `<b>${format_currency(
						offer.rate,
						"ALL",
						0
				  )}</b><span class="text-muted small"> / ${esc(__(offer.uom))}</span>`;
		const qty = can_add
			? `<div class="hat-mp-stepper">
					<button class="btn btn-default btn-xs" data-step="-1" aria-label="${__("Less")}">−</button>
					<input type="number" class="form-control input-xs hat-mp-qty" min="${esc(
						String(offer.minimum_qty || 1)
					)}" value="${esc(String(offer.minimum_qty || 1))}" aria-label="${__(
					"Quantity"
			  )}">
					<button class="btn btn-default btn-xs" data-step="1" aria-label="${__("More")}">+</button>
				</div>`
			: "<div></div>";
		const more =
			count > 1
				? ` · <a href="#" data-show-offers>${
						count === 2 ? __("+1 offer") : __("+{0} offers", [count - 1])
				  }</a>`
				: "";
		return `
			<div class="hat-mp-card hat-mp-row-card" data-product="${esc(product.name)}">
				<div class="hat-mp-row">
					<div class="hat-mp-thumb">${this.image_html(product)}</div>
					<div class="hat-mp-row-title">
						${this.name_html(product)}
						<div class="text-muted small">${esc(product.item_group)} · ${this.distributor_html(
			offer
		)}${more}</div>
					</div>
					<div class="hat-mp-row-price">${price}</div>
					${qty}
					<div class="hat-mp-row-action">${
						offer.availability !== "Available"
							? this.status_pill(product, offer)
							: this.action_html(product, offer, { small: true, label: __("Add") })
					}</div>
				</div>
				${this.compare_html(product)}
			</div>`;
	}

	offer_html(offer) {
		this.offers[offer.name] = offer;
		const esc = frappe.utils.escape_html;
		const rating = offer.distributor_rating
			? `<span class="hat-mp-rating">★ ${(offer.distributor_rating * 5).toFixed(1)}</span>`
			: "";
		const details = [
			__("min. {0} {1}", [offer.minimum_qty, __(offer.uom)]),
			offer.lead_time_days ? __("{0} days", [offer.lead_time_days]) : null,
		]
			.filter(Boolean)
			.join(" · ");
		let action;
		if (offer.availability !== "Available") {
			action = `<span class="indicator-pill red">${__("Out of Stock")}</span>`;
		} else if (hat.marketplace.can_order()) {
			action = `<button class="btn btn-xs btn-primary" data-add-listing="${esc(offer.name)}">
				${__("Add to cart")}</button>`;
		} else {
			action = "";
		}
		return `
			<div class="hat-mp-offer">
				<div class="hat-mp-distributor">
					<a href="#" data-filter-distributor="${esc(offer.distributor)}"
						title="${esc(__("Show only {0}'s products", [offer.distributor_name]))}">${esc(
			offer.distributor_name
		)}</a>
					<a class="hat-mp-offer-link text-muted" href="/desk/hat-listing/${encodeURIComponent(
						offer.name
					)}" title="${esc(__("Offer details"))}">${frappe.utils.icon(
			"external-link",
			"xs"
		)}</a>
					${rating}
					${offer.best_price ? `<span class="indicator-pill green">${__("Best price")}</span>` : ""}
					<div class="text-muted small">${esc(details)}</div>
				</div>
				<div class="hat-mp-price">${this.price_html(offer)}</div>
				<div class="hat-mp-action">${action}</div>
			</div>`;
	}

	price_html(offer) {
		if (offer.rate === null) {
			return `<span class="text-muted small">${__("Price on request")}</span>`;
		}
		const unit = `<span class="text-muted small"> / ${frappe.utils.escape_html(
			__(offer.uom)
		)}</span>`;
		if (offer.tiers && offer.tiers.length) {
			const lowest = Math.min(...offer.tiers.map((t) => t.rate));
			const ranges = offer.tiers
				.map(
					(t, i) =>
						`${hat.marketplace.tier_label(offer.tiers, i)}: ${format_currency(
							t.rate,
							"ALL",
							0
						)}`
				)
				.join("<br>");
			return `<span class="text-muted small">${__("from")}</span> <b>${format_currency(
				lowest,
				"ALL",
				0
			)}</b>${unit}<div class="text-muted small hat-mp-tiers">${ranges}</div>`;
		}
		const rate = `<b>${format_currency(offer.rate, "ALL", 0)}</b>${unit}`;
		if (offer.rate < offer.price) {
			return `${rate}<div class="text-muted small"><s>${format_currency(
				offer.price,
				"ALL",
				0
			)}</s></div>`;
		}
		return rate;
	}
}

frappe.dom.set_style(`
	.hat-marketplace { padding: var(--padding-md) 0; }
	.hat-mp-summary { margin-bottom: var(--margin-md); }
	.hat-mp-more { text-align: center; margin-top: var(--margin-md); }
	.hat-mp-empty { padding: var(--padding-lg); }
	.hat-mp-grid { display: grid; gap: var(--margin-md); }
	.hat-mp-card {
		background: var(--card-bg);
		border: 1px solid var(--border-color);
		border-radius: var(--border-radius-lg);
		overflow: hidden;
		min-width: 0;
	}
	.hat-mp-name { display: block; font-weight: 600; color: var(--heading-color); line-height: 1.3; }
	a.hat-mp-name:hover { text-decoration: underline; }
	.hat-mp-image-link { display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; }
	.hat-mp-rating { color: var(--yellow-600, #d97706); }
	.hat-mp-photo, .hat-mp-thumb {
		background: #fff;
		display: flex; align-items: center; justify-content: center;
		position: relative; overflow: hidden;
		color: var(--text-muted); font-weight: 600;
	}
	.hat-mp-photo img, .hat-mp-thumb img { max-width: 100%; max-height: 100%; object-fit: contain; }
	.hat-mp-big-price { font-size: var(--text-xl); font-weight: 600; color: var(--heading-color); margin-top: var(--margin-xs); }
	.hat-mp-big-price.text-muted { font-size: var(--text-base); color: var(--text-muted); }
	.hat-mp-from { font-size: var(--text-sm); font-weight: 400; color: var(--text-muted); }
	.hat-mp-compare-link { font-size: var(--text-sm); text-align: center; }
	.hat-mp-compare { border-top: 1px solid var(--border-color); padding: 0 var(--padding-md) var(--padding-sm); }
	.hat-mp-offer {
		display: grid;
		grid-template-columns: 1fr auto auto;
		gap: var(--padding-sm);
		align-items: center;
		padding-top: var(--padding-sm);
	}
	.hat-mp-offer + .hat-mp-offer { border-top: 1px solid var(--border-color); margin-top: var(--padding-sm); }
	.hat-mp-price { text-align: right; white-space: nowrap; }

	/* A: grid */
	.hat-mp-view-grid { grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); }
	.hat-mp-tile { display: flex; flex-direction: column; }
	.hat-mp-tile .hat-mp-photo { height: 180px; padding: var(--padding-md); border-bottom: 1px solid var(--border-color); }
	.hat-mp-badge { position: absolute; top: var(--padding-sm); left: var(--padding-sm); }
	.hat-mp-tile .hat-mp-body { padding: var(--padding-md); display: flex; flex-direction: column; gap: 2px; flex: 1; }
	.hat-mp-actions { margin-top: auto; padding-top: var(--padding-sm); display: flex; flex-direction: column; gap: var(--padding-xs); }
	.hat-mp-actions .hat-mp-btn { width: 100%; }

	/* B: supplier cards */
	/* as many cards per row as fit at 440px or more each */
	.hat-mp-view-supplier { grid-template-columns: repeat(auto-fill, minmax(min(440px, 100%), 1fr)); }
	.hat-mp-wide { container-type: inline-size; }
	.hat-mp-wide-row { display: grid; grid-template-columns: 110px minmax(0, 1fr) 150px; height: 100%; }
	.hat-mp-wide .hat-mp-photo { padding: var(--padding-sm); border-right: 1px solid var(--border-color); min-height: 120px; }
	.hat-mp-wide .hat-mp-photo img { max-height: 100px; }
	.hat-mp-wide .hat-mp-big-price { font-size: var(--text-lg); }
	.hat-mp-wide .hat-mp-body { padding: var(--padding-sm) var(--padding-md); display: flex; flex-direction: column; gap: var(--padding-xs); }
	.hat-mp-pills { display: flex; flex-wrap: wrap; gap: var(--padding-xs); }
	.hat-mp-buy {
		padding: var(--padding-sm) var(--padding-md);
		border-left: 1px solid var(--border-color);
		display: flex; flex-direction: column; justify-content: center; gap: var(--padding-xs);
	}
	.hat-mp-buy .hat-mp-big-price { margin-top: 0; }
	/* a card squeezed below 440px puts the price and button under the details */
	@container (max-width: 439px) {
		.hat-mp-wide-row { grid-template-columns: 96px minmax(0, 1fr); }
		.hat-mp-buy { grid-column: 1 / -1; border-left: 0; border-top: 1px solid var(--border-color); }
	}

	/* C: compact list */
	.hat-mp-view-compact { grid-template-columns: 1fr; gap: 0; border: 1px solid var(--border-color); border-radius: var(--border-radius-lg); overflow: hidden; }
	.hat-mp-view-compact .hat-mp-card { border: 0; border-radius: 0; }
	.hat-mp-view-compact .hat-mp-card + .hat-mp-card { border-top: 1px solid var(--border-color); }
	.hat-mp-row {
		display: grid;
		grid-template-columns: 48px minmax(0, 1fr) 140px 130px 100px;
		gap: var(--padding-md);
		align-items: center;
		padding: var(--padding-sm) var(--padding-md);
	}
	.hat-mp-thumb { width: 48px; height: 48px; border: 1px solid var(--border-color); border-radius: var(--border-radius); padding: 3px; }
	.hat-mp-row-price { white-space: nowrap; }
	.hat-mp-stepper { display: flex; align-items: center; gap: 4px; }
	.hat-mp-stepper .hat-mp-qty { width: 56px; text-align: center; padding: 0 4px; }
	.hat-mp-row-action { text-align: right; }
	.hat-mp-row-action .hat-mp-btn { width: 100%; }

	@media (max-width: 768px) {
		.hat-mp-row { grid-template-columns: 48px minmax(0, 1fr) auto; }
		.hat-mp-row .hat-mp-stepper, .hat-mp-row .hat-mp-row-action { grid-column: 2 / -1; }
		.hat-mp-row .hat-mp-row-action { text-align: left; }
	}
`);
