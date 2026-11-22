// One product as a hotel sees it before buying: details, every distributor's offer side by side,
// who those distributors are, and other products of the same category.
// Route: /desk/hat-product/<item code>

frappe.pages["hat-product"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Product"),
		single_column: true,
	});
	wrapper.product_page = new HATProductPage(page);
};

frappe.pages["hat-product"].on_page_show = (wrapper) => {
	wrapper.product_page.load(frappe.get_route()[1]);
};

const PRODUCT_API = "hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing";
const product_url = (code) => `/desk/hat-product/${encodeURIComponent(code)}`;

class HATProductPage {
	constructor(page) {
		this.page = page;
		this.offers = {};
		this.$body = $(`<div class="hat-product"></div>`).appendTo(page.main);
		this.page.set_secondary_action(
			__("Marketplace"),
			() => frappe.set_route("hat-marketplace"),
			"store"
		);

		if (frappe.user.has_role("HAT Staff") || frappe.user.has_role("System Manager")) {
			this.hotel_field = this.page.add_field({
				fieldname: "hotel",
				fieldtype: "Link",
				options: "Customer",
				label: __("Prices for hotel"),
				get_query: () => ({ filters: { customer_group: "Hotel" } }),
				change: () => this.load(this.item),
			});
		}

		this.$body.on("click", "[data-add-listing]", (e) => {
			const offer = this.offers[$(e.currentTarget).attr("data-add-listing")];
			hat.marketplace.add_to_order(offer, this.hotel || undefined);
		});
		this.$body.on("click", "[data-request-quotes]", () => {
			hat.marketplace.request_quotes(this.data.product, this.hotel || undefined);
		});
		this.$body.on("click", "[data-distributor-products]", (e) => {
			e.preventDefault();
			frappe.route_options = {
				distributor: $(e.currentTarget).attr("data-distributor-products"),
			};
			frappe.set_route("hat-marketplace");
		});
		this.$body.on("click", "[data-goto-distributor]", (e) => {
			e.preventDefault();
			const target = this.$body.find(
				`[data-distributor="${CSS.escape(
					$(e.currentTarget).attr("data-goto-distributor")
				)}"]`
			)[0];
			target?.scrollIntoView({ behavior: "smooth", block: "center" });
		});
	}

	async load(item) {
		if (!item) {
			frappe.set_route("hat-marketplace");
			return;
		}
		this.item = item;
		this.$body.html(`<div class="text-muted hat-pp-loading">${__("Loading…")}</div>`);
		let message;
		try {
			({ message } = await frappe.call({
				method: `${PRODUCT_API}.get_product`,
				args: { item, hotel: this.hotel_field?.get_value() || null },
			}));
		} catch {
			this.$body.html(
				`<div class="text-muted hat-pp-loading">${__(
					"This product is not on the marketplace."
				)} <a href="/desk/hat-marketplace">${__("Back to the Marketplace")}</a></div>`
			);
			return;
		}
		this.data = message;
		this.hotel = message.hotel;
		this.offers = {};
		message.offers.forEach((offer) => (this.offers[offer.name] = offer));
		this.page.set_title(message.product.item_name);
		this.$body.html(
			[
				this.summary_html(),
				this.offers_html(),
				this.distributors_html(),
				this.related_html(),
			].join("")
		);
	}

	// Lowest price over every available offer and quantity range
	lowest_rate() {
		const rates = this.data.offers
			.filter((o) => o.availability === "Available" && o.rate !== null)
			.flatMap((o) => (o.tiers && o.tiers.length ? o.tiers.map((t) => t.rate) : [o.rate]));
		return rates.length ? Math.min(...rates) : null;
	}

	summary_html() {
		const esc = frappe.utils.escape_html;
		const { product, offers } = this.data;
		const best = offers[0];
		const lowest = this.lowest_rate();
		const available = offers.some((o) => o.availability === "Available");
		const image = product.image
			? `<img src="${encodeURI(product.image)}" alt="${esc(product.item_name)}">`
			: `<span>${esc(frappe.get_abbr(product.item_name))}</span>`;
		const price =
			lowest === null
				? `<div class="hat-pp-price text-muted">${__("Price on request")}</div>`
				: `<div class="hat-pp-price">${
						offers.length > 1 || (best.tiers || []).length
							? `<span class="hat-pp-from">${__("from")}</span> `
							: ""
				  }${format_currency(lowest, "ALL", 0)}<span class="hat-pp-unit"> / ${esc(
						__(product.stock_uom)
				  )}</span></div>`;
		const pills = [
			available
				? `<span class="indicator-pill green">${__("In stock")}</span>`
				: `<span class="indicator-pill red">${__("Out of stock")}</span>`,
			`<span class="indicator-pill blue">${
				offers.length === 1 ? __("1 distributor") : __("{0} distributors", [offers.length])
			}</span>`,
		].join(" ");
		const actions = [];
		if (best.availability === "Available" && hat.marketplace.can_order()) {
			actions.push(
				`<button class="btn btn-primary" data-add-listing="${esc(best.name)}">${__(
					"Add to cart"
				)}</button>`
			);
		}
		if (frappe.model.can_create("HAT Quote Request")) {
			actions.push(
				`<button class="btn btn-default" data-request-quotes
					title="${__("Ask all distributors of this category for a price")}">${__("Request quote")}</button>`
			);
		}
		const best_note =
			best.availability === "Available" && actions.length && offers.length > 1
				? `<div class="text-muted small">${__(
						"Add to cart uses the best offer, from {0}.",
						[esc(best.distributor_name)]
				  )}</div>`
				: "";
		const partner_note = this.hotel
			? __("Prices for {0}. Partner prices are shown where you have a partnership.", [
					esc(this.hotel),
			  ])
			: __("Public prices.");
		return `
			<div class="hat-pp-card hat-pp-summary">
				<div class="hat-pp-photo">${image}</div>
				<div class="hat-pp-info">
					<div class="text-muted small">
						<a href="/desk/hat-marketplace">${__("Marketplace")}</a> › ${esc(product.item_group)}
					</div>
					<h2 class="hat-pp-title">${esc(product.item_name)}</h2>
					<div class="text-muted small">${esc(product.name)} · ${__("Unit")}: ${esc(
			__(product.stock_uom)
		)}</div>
					<div class="hat-pp-pills">${pills}</div>
					${price}
					<div class="text-muted small">${partner_note}</div>
					<div class="hat-pp-actions">${actions.join("")}</div>
					${best_note}
					${
						product.description
							? `<div class="hat-pp-description">
								<div class="hat-pp-label">${__("Description")}</div>
								<div class="hat-pp-text">${product.description}</div>
							</div>`
							: ""
					}
				</div>
			</div>`;
	}

	price_cell(offer) {
		if (offer.rate === null) return `<span class="text-muted">${__("On request")}</span>`;
		const esc = frappe.utils.escape_html;
		const unit = `<span class="text-muted small"> / ${esc(__(offer.uom))}</span>`;
		if (offer.tiers && offer.tiers.length) {
			const rows = offer.tiers
				.map(
					(t, i) =>
						`<div>${hat.marketplace.tier_label(offer.tiers, i)}: <b>${format_currency(
							t.rate,
							"ALL",
							0
						)}</b>${
							t.rate < t.price
								? ` <s class="text-muted">${format_currency(
										t.price,
										"ALL",
										0
								  )}</s>`
								: ""
						}</div>`
				)
				.join("");
			return `<div class="small">${rows}</div><div class="text-muted small">${__("per {0}", [
				esc(__(offer.uom)),
			])}</div>`;
		}
		const was =
			offer.rate < offer.price
				? `<div class="text-muted small"><s>${format_currency(
						offer.price,
						"ALL",
						0
				  )}</s> ${__("public price")}</div>`
				: "";
		return `<b>${format_currency(offer.rate, "ALL", 0)}</b>${unit}${was}`;
	}

	offers_html() {
		const esc = frappe.utils.escape_html;
		const rows = this.data.offers
			.map((offer) => {
				const rating = offer.distributor_rating
					? `<span class="hat-pp-rating">★ ${(offer.distributor_rating * 5).toFixed(
							1
					  )}</span>`
					: `<span class="text-muted small">${__("No ratings yet")}</span>`;
				let action = "";
				if (offer.availability !== "Available") {
					action = `<span class="indicator-pill red">${__("Out of stock")}</span>`;
				} else if (hat.marketplace.can_order()) {
					action = `<button class="btn btn-xs btn-primary" data-add-listing="${esc(
						offer.name
					)}">${__("Add to cart")}</button>`;
				}
				return `
					<tr>
						<td>
							<a href="#" data-goto-distributor="${esc(offer.distributor)}">${esc(offer.distributor_name)}</a>
							${offer.best_price ? ` <span class="indicator-pill green">${__("Best price")}</span>` : ""}
							<div class="text-muted small">${esc(offer.title)}</div>
						</td>
						<td>${rating}</td>
						<td>${this.price_cell(offer)}</td>
						<td>${esc(String(offer.minimum_qty))} ${esc(__(offer.uom))}</td>
						<td>${offer.lead_time_days ? __("{0} days", [offer.lead_time_days]) : "–"}</td>
						<td class="text-right">${action}</td>
					</tr>`;
			})
			.join("");
		return `
			<div class="hat-pp-section">
				<h4>${__("Compare offers")}</h4>
				<div class="hat-pp-card hat-pp-table-wrap">
					<table class="table hat-pp-table">
						<thead><tr>
							<th>${__("Distributor")}</th>
							<th>${__("Rating")}</th>
							<th>${__("Price")}</th>
							<th>${__("Minimum order")}</th>
							<th>${__("Lead time")}</th>
							<th></th>
						</tr></thead>
						<tbody>${rows}</tbody>
					</table>
				</div>
			</div>`;
	}

	distributors_html() {
		const esc = frappe.utils.escape_html;
		const cards = this.data.distributors
			.map((d) => {
				const rating = d.hat_average_rating
					? `<span class="hat-pp-rating">★ ${(d.hat_average_rating * 5).toFixed(
							1
					  )}</span> ${__("from hotels")}`
					: __("No ratings yet");
				const region =
					d.delivers_to_hotel === true
						? `<span class="indicator-pill green">${__(
								"Delivers to your region"
						  )}</span>`
						: d.delivers_to_hotel === false
						? `<span class="indicator-pill orange">${__("Not in your region")}</span>`
						: "";
				const contact = [
					d.email_id
						? `<a href="mailto:${esc(d.email_id)}">${frappe.utils.icon(
								"mail",
								"xs"
						  )} ${esc(d.email_id)}</a>`
						: "",
					d.mobile_no
						? `<a href="tel:${esc(d.mobile_no)}">${frappe.utils.icon(
								"phone",
								"xs"
						  )} ${esc(d.mobile_no)}</a>`
						: "",
					d.website
						? `<a href="${esc(
								d.website
						  )}" target="_blank" rel="noopener noreferrer">${esc(d.website)}</a>`
						: "",
				]
					.filter(Boolean)
					.join("");
				const facts = [
					[__("Rating"), rating],
					[
						__("Delivers to"),
						d.coverage.length
							? d.coverage.map((t) => esc(t)).join(", ")
							: __("All regions"),
					],
					[
						__("Minimum order value"),
						d.hat_minimum_order
							? format_currency(d.hat_minimum_order, "ALL", 0)
							: __("None"),
					],
				]
					.map(
						([label, value]) =>
							`<div class="hat-pp-fact"><span class="text-muted">${label}</span><span>${value}</span></div>`
					)
					.join("");
				return `
					<div class="hat-pp-card hat-pp-distributor" data-distributor="${esc(d.name)}">
						<div class="hat-pp-distributor-head">
							<b>${esc(d.supplier_name)}</b>
							${d.hat_verified ? `<span class="indicator-pill green">${__("Verified by Hatix")}</span>` : ""}
							${region}
						</div>
						${facts}
						${contact ? `<div class="hat-pp-contact">${contact}</div>` : ""}
						<a class="small" href="/desk/hat-distributor/${encodeURIComponent(d.name)}">${__(
					"About this distributor and reviews"
				)}</a>
						<a class="small" href="#" data-distributor-products="${esc(d.name)}">${__(
					"All products from this distributor"
				)}</a>
					</div>`;
			})
			.join("");
		return `
			<div class="hat-pp-section">
				<h4>${__("Distributors")}</h4>
				<div class="hat-pp-distributors">${cards}</div>
			</div>`;
	}

	related_html() {
		const esc = frappe.utils.escape_html;
		const { related, product } = this.data;
		if (!related.length) return "";
		const cards = related
			.map((item) => {
				const image = item.image
					? `<img src="${encodeURI(item.image)}" alt="" loading="lazy">`
					: `<span>${esc(frappe.get_abbr(item.item_name))}</span>`;
				const price =
					item.lowest_rate === null
						? `<span class="text-muted small">${__("Price on request")}</span>`
						: `<b>${format_currency(item.lowest_rate, "ALL", 0)}</b>`;
				return `
					<a class="hat-pp-card hat-pp-related-card" href="${product_url(item.name)}">
						<div class="hat-pp-related-photo">${image}</div>
						<div class="hat-pp-related-name">${esc(item.item_name)}</div>
						<div>${price}</div>
						<div class="text-muted small">${
							item.offer_count === 1
								? __("1 distributor")
								: __("{0} distributors", [item.offer_count])
						}</div>
					</a>`;
			})
			.join("");
		return `
			<div class="hat-pp-section">
				<h4>${__("More in {0}", [esc(product.item_group)])}</h4>
				<div class="hat-pp-related">${cards}</div>
			</div>`;
	}
}

frappe.dom.set_style(`
	.hat-product { padding: var(--padding-md) 0 var(--padding-xl); display: flex; flex-direction: column; gap: var(--margin-lg); }
	.hat-pp-loading { padding: var(--padding-lg); }
	.hat-pp-card {
		background: var(--card-bg);
		border: 1px solid var(--border-color);
		border-radius: var(--border-radius-lg);
		overflow: hidden;
	}
	.hat-pp-section h4 { margin-bottom: var(--margin-sm); }
	.hat-pp-rating { color: var(--yellow-600, #d97706); }

	.hat-pp-summary { display: grid; grid-template-columns: minmax(220px, 360px) minmax(0, 1fr); }
	.hat-pp-photo {
		background: #fff; display: flex; align-items: center; justify-content: center;
		padding: var(--padding-lg); border-right: 1px solid var(--border-color); min-height: 300px;
		color: var(--text-muted); font-size: 2rem; font-weight: 600;
	}
	.hat-pp-photo img { max-width: 100%; max-height: 340px; object-fit: contain; }
	.hat-pp-info { padding: var(--padding-lg); display: flex; flex-direction: column; gap: var(--padding-xs); }
	.hat-pp-title { margin: 0; font-size: var(--text-2xl); }
	.hat-pp-pills { display: flex; flex-wrap: wrap; gap: var(--padding-xs); margin: var(--margin-xs) 0; }
	.hat-pp-price { font-size: var(--text-2xl); font-weight: 600; color: var(--heading-color); }
	.hat-pp-price.text-muted { font-size: var(--text-lg); color: var(--text-muted); }
	.hat-pp-from, .hat-pp-unit { font-size: var(--text-base); font-weight: 400; color: var(--text-muted); }
	.hat-pp-actions { display: flex; flex-wrap: wrap; gap: var(--padding-sm); margin-top: var(--margin-sm); }
	.hat-pp-description { margin-top: var(--margin-md); padding-top: var(--padding-md); border-top: 1px solid var(--border-color); }
	.hat-pp-label { font-weight: 600; margin-bottom: var(--margin-xs); }
	.hat-pp-text { color: var(--text-color); line-height: 1.6; max-width: 70ch; }

	.hat-pp-table-wrap { overflow-x: auto; }
	.hat-pp-table { margin: 0; min-width: 640px; }
	.hat-pp-table th { font-weight: 500; color: var(--text-muted); font-size: var(--text-sm); white-space: nowrap; }
	.hat-pp-table td, .hat-pp-table th { padding: var(--padding-sm) var(--padding-md); vertical-align: middle; }

	.hat-pp-distributors { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr)); gap: var(--margin-md); }
	.hat-pp-distributor { padding: var(--padding-md); display: flex; flex-direction: column; gap: var(--padding-xs); }
	.hat-pp-distributor-head { display: flex; flex-wrap: wrap; align-items: center; gap: var(--padding-xs); margin-bottom: var(--margin-xs); }
	.hat-pp-fact { display: flex; justify-content: space-between; gap: var(--padding-md); font-size: var(--text-sm); }
	.hat-pp-fact span:last-child { text-align: right; }
	.hat-pp-contact { display: flex; flex-direction: column; gap: 2px; font-size: var(--text-sm); padding-top: var(--padding-xs); border-top: 1px solid var(--border-color); }

	.hat-pp-related { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: var(--margin-md); }
	.hat-pp-related-card { padding: var(--padding-sm); display: flex; flex-direction: column; gap: 2px; color: inherit; text-decoration: none; }
	.hat-pp-related-card:hover { border-color: var(--gray-400); text-decoration: none; }
	.hat-pp-related-photo { height: 110px; background: #fff; display: flex; align-items: center; justify-content: center; margin-bottom: var(--margin-xs); color: var(--text-muted); font-weight: 600; }
	.hat-pp-related-photo img { max-width: 100%; max-height: 100%; object-fit: contain; }
	.hat-pp-related-name { font-weight: 600; color: var(--heading-color); line-height: 1.3; }

	@media (max-width: 768px) {
		.hat-pp-summary { grid-template-columns: 1fr; }
		.hat-pp-photo { border-right: 0; border-bottom: 1px solid var(--border-color); min-height: 200px; }
	}
`);
