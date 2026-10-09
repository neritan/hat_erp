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
	wrapper.marketplace.refresh();
};

const MARKETPLACE_API = "hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing";
const is_staff = () => frappe.user.has_role("HAT Staff") || frappe.user.has_role("System Manager");

class HATMarketplace {
	constructor(page) {
		this.page = page;
		this.page_length = 24;
		this.offers = {};
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
			hat.marketplace.add_to_order(offer, this.hotel || undefined);
		});
		this.$more.on("click", "button", () => this.refresh(true));
		this.page.set_secondary_action(__("Refresh"), () => this.refresh(), "refresh");
	}

	make_filters() {
		const refresh = frappe.utils.debounce(() => this.refresh(), 300);
		this.search = this.page.add_field({
			fieldname: "search",
			fieldtype: "Data",
			label: __("Search product or distributor"),
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
		if (is_staff()) {
			this.hotel_field = this.page.add_field({
				fieldname: "hotel",
				fieldtype: "Link",
				options: "Customer",
				label: __("Prices for hotel"),
				get_query: () => ({ filters: { customer_group: "Hotel" } }),
				change: refresh,
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
				hotel: this.hotel_field?.get_value() || null,
				available_only: this.available_only.get_value() ? 1 : 0,
				in_my_region: this.in_my_region?.get_value() ? 1 : 0,
				start,
				page_length: this.page_length,
			},
		});
		this.hotel = message.hotel;
		if (!append) {
			this.$grid.empty();
			this.offers = {};
			this.loaded = 0;
		}
		this.loaded += message.products.length;
		message.products.forEach((product) => this.$grid.append(this.product_html(product)));
		this.$summary.text(
			this.hotel
				? __("Prices for {0}. Partner prices are shown where you have a partnership.", [
						this.hotel,
				  ])
				: __("Public prices. Choose a hotel to see its partner prices.")
		);
		if (!this.loaded) {
			this.$grid.html(
				`<div class="hat-mp-empty text-muted">${__(
					"No products match these filters."
				)}</div>`
			);
		}
		this.$more.html(
			message.has_more
				? `<button class="btn btn-default btn-sm">${__("Load more products")}</button>`
				: ""
		);
	}

	product_html(product) {
		const esc = frappe.utils.escape_html;
		const image = product.image
			? `<img src="${encodeURI(product.image)}" alt="">`
			: `<span>${esc(frappe.get_abbr(product.item_name))}</span>`;
		const count = product.offers.length;
		return `
			<div class="hat-mp-card">
				<div class="hat-mp-head">
					<div class="hat-mp-image">${image}</div>
					<div class="hat-mp-title">
						<div class="hat-mp-name">${esc(product.item_name)}</div>
						<div class="text-muted small">${esc(product.item_group)}</div>
					</div>
					<span class="indicator-pill ${count > 1 ? "blue" : "gray"}">
						${count === 1 ? __("1 distributor") : __("{0} distributors", [count])}
					</span>
				</div>
				<div class="hat-mp-offers">
					${product.offers.map((offer) => this.offer_html(offer)).join("")}
				</div>
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
				${offer.rate === null ? __("Request Quote") : __("Add to Order")}</button>`;
		} else {
			action = "";
		}
		return `
			<div class="hat-mp-offer">
				<div class="hat-mp-distributor">
					<a href="/desk/hat-listing/${encodeURIComponent(offer.name)}">${esc(offer.distributor_name)}</a>
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
	.hat-mp-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
		gap: var(--margin-md);
	}
	.hat-mp-card {
		background: var(--card-bg);
		border: 1px solid var(--border-color);
		border-radius: var(--border-radius-lg);
		padding: var(--padding-md);
		display: flex;
		flex-direction: column;
		gap: var(--padding-sm);
	}
	.hat-mp-head { display: flex; align-items: flex-start; gap: var(--padding-sm); }
	.hat-mp-title { flex: 1; min-width: 0; }
	.hat-mp-name { font-weight: 600; color: var(--heading-color); }
	.hat-mp-image {
		width: 48px; height: 48px; flex: none;
		border-radius: var(--border-radius);
		background: var(--subtle-fg);
		display: flex; align-items: center; justify-content: center;
		overflow: hidden; color: var(--text-muted); font-weight: 600;
	}
	.hat-mp-image img { width: 100%; height: 100%; object-fit: cover; }
	.hat-mp-offer {
		display: grid;
		grid-template-columns: 1fr auto auto;
		gap: var(--padding-sm);
		align-items: center;
		padding-top: var(--padding-sm);
		border-top: 1px solid var(--border-color);
	}
	.hat-mp-rating { color: var(--yellow-600, #d97706); font-size: var(--text-sm); margin-left: 4px; }
	.hat-mp-price { text-align: right; white-space: nowrap; }
	.hat-mp-more { text-align: center; margin-top: var(--margin-md); }
	.hat-mp-empty { padding: var(--padding-lg); }
`);
