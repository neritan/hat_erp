// A distributor as hotels see it, read-only: who they are, where they deliver, how hotels rate them,
// and what they sell. Hotels land here instead of the Supplier form.
// Route: /desk/hat-distributor/<supplier>

frappe.pages["hat-distributor"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Distributor"),
		single_column: true,
	});
	wrapper.distributor_page = new HATDistributorPage(page);
};

frappe.pages["hat-distributor"].on_page_show = (wrapper) => {
	wrapper.distributor_page.load(frappe.get_route()[1]);
};

class HATDistributorPage {
	constructor(page) {
		this.page = page;
		this.$body = $(`<div class="hat-profile"></div>`).appendTo(page.main);
		this.page.set_secondary_action(
			__("Marketplace"),
			() => frappe.set_route("hat-marketplace"),
			"store"
		);
		this.$body.on("click", "[data-review]", () =>
			hat.reviews.open({
				distributor: this.name,
				hotel: this.data.hotel,
				on_saved: () => this.load(this.name),
			})
		);
		this.$body.on("click", "[data-rate-order]", (e) =>
			hat.reviews.open({
				distributor: this.name,
				order_request: $(e.currentTarget).attr("data-rate-order"),
				hotel: this.data.hotel,
				on_saved: () => this.load(this.name),
			})
		);
		this.$body.on("click", "[data-products]", (e) => {
			e.preventDefault();
			frappe.route_options = { distributor: this.name };
			frappe.set_route("hat-marketplace");
		});
	}

	async load(name) {
		if (!name) {
			frappe.set_route("hat-marketplace");
			return;
		}
		this.name = name;
		this.$body.html(`<div class="text-muted hat-profile-loading">${__("Loading…")}</div>`);
		try {
			const { message } = await frappe.call({
				method: "hat.hospitality_and_tourism_academy.page.hat_distributor.hat_distributor.get_distributor",
				args: { distributor: name },
			});
			this.data = message;
		} catch {
			this.$body.html(
				`<div class="text-muted hat-profile-loading">${__(
					"This distributor is not available."
				)} <a href="/desk/hat-marketplace">${__("Back to the Marketplace")}</a></div>`
			);
			return;
		}
		this.page.set_title(this.data.distributor.supplier_name);
		this.$body.html(
			[
				this.header_html(),
				this.with_hotel_html(),
				this.products_html(),
				this.reviews_html(),
			].join("")
		);
	}

	header_html() {
		const esc = frappe.utils.escape_html;
		const d = this.data.distributor;
		const scores = this.data.scores;
		const logo = d.image
			? `<img src="${encodeURI(d.image)}" alt="${esc(d.supplier_name)}">`
			: `<span>${esc(frappe.get_abbr(d.supplier_name))}</span>`;
		const pills = [
			d.hat_verified
				? `<span class="indicator-pill green">${__("Verified by Hatix")}</span>`
				: "",
			d.delivers_to_hotel === true
				? `<span class="indicator-pill green">${__("Delivers to your region")}</span>`
				: d.delivers_to_hotel === false
				? `<span class="indicator-pill orange">${__("Not in your region")}</span>`
				: "",
		].join(" ");
		const own_review = this.data.with_hotel?.review;
		const actions = [
			`<button class="btn btn-default" data-products>${__("See products")}</button>`,
			this.data.can_review
				? `<button class="btn btn-primary" data-review>${
						own_review ? __("Edit your review") : __("Write a review")
				  }</button>`
				: "",
		].join("");
		const facts = [
			[__("Rating"), hat.profile.stars(scores.rating, scores.count)],
			[
				__("Delivers to"),
				d.coverage.length ? d.coverage.map((t) => esc(t)).join(", ") : __("All regions"),
			],
			[
				__("Minimum order value"),
				d.hat_minimum_order ? format_currency(d.hat_minimum_order, "ALL", 0) : __("None"),
			],
			[__("Product quality"), hat.profile.stars(scores.quality)],
			[__("Delivery"), hat.profile.stars(scores.delivery)],
			[__("Communication"), hat.profile.stars(scores.communication)],
		];
		const contact = hat.profile.contact(d);
		return `
			<div class="hat-profile-card hat-profile-head">
				<div class="hat-profile-logo">${logo}</div>
				<div class="hat-profile-info">
					<h2 class="hat-profile-title">${esc(d.supplier_name)}</h2>
					<div class="hat-profile-pills">${pills}</div>
					${
						d.categories.length
							? `<div class="hat-profile-tags">${d.categories
									.map((c) => `<span class="hat-profile-tag">${esc(c)}</span>`)
									.join("")}</div>`
							: ""
					}
					${d.supplier_details ? `<div class="hat-profile-text">${esc(d.supplier_details)}</div>` : ""}
					<div class="hat-profile-actions">${actions}</div>
				</div>
				<div class="hat-profile-side">
					${hat.profile.facts(facts)}
					${contact}
				</div>
			</div>`;
	}

	with_hotel_html() {
		const w = this.data.with_hotel;
		if (!w) return "";
		const esc = frappe.utils.escape_html;
		const to_rate = w.to_rate.length
			? `<div class="hat-profile-rate">
				<span class="text-muted small">${__("Completed orders to rate")}:</span>
				${w.to_rate
					.map(
						(o) =>
							`<button class="btn btn-xs btn-default" data-rate-order="${esc(
								o
							)}">★ ${esc(o)}</button>`
					)
					.join(" ")}
			</div>`
			: "";
		return `
			<div class="hat-profile-section">
				<h4>${__("With your hotel")}</h4>
				<div class="hat-profile-card hat-profile-stats">
					${hat.profile.stat(__("Order requests"), w.orders)}
					${hat.profile.stat(__("Ordered"), format_currency(w.ordered, "ALL", 0))}
					${hat.profile.stat(
						__("Last request"),
						w.last_order ? frappe.datetime.str_to_user(w.last_order) : "–"
					)}
					${hat.profile.stat(
						__("Your review"),
						w.review ? hat.profile.stars(w.review.rating) : __("Not yet")
					)}
				</div>
				${to_rate}
			</div>`;
	}

	products_html() {
		const esc = frappe.utils.escape_html;
		const { listings, total } = this.data.products;
		if (!listings.length) return "";
		const cards = listings
			.map((l) => {
				const image = l.image
					? `<img src="${encodeURI(l.image)}" alt="" loading="lazy">`
					: `<span>${esc(frappe.get_abbr(l.title || l.item))}</span>`;
				const price =
					l.price_type === "Price on Request" || !l.price
						? `<span class="text-muted small">${__("Price on request")}</span>`
						: `<b>${format_currency(
								l.price,
								"ALL",
								0
						  )}</b> <span class="text-muted small">/ ${esc(__(l.uom || ""))}</span>`;
				return `
					<a class="hat-profile-card hat-profile-product" href="/desk/hat-product/${encodeURIComponent(
						l.item
					)}">
						<div class="hat-profile-product-photo">${image}</div>
						<div class="hat-profile-product-name">${esc(l.title || l.item)}</div>
						<div class="text-muted small">${esc(l.item_group || "")}</div>
						<div>${price}</div>
						${
							l.availability === "Out of Stock"
								? `<span class="indicator-pill red">${__("Out of stock")}</span>`
								: ""
						}
					</a>`;
			})
			.join("");
		const more =
			total > listings.length
				? `<a href="#" data-products class="small">${__("All {0} products", [total])}</a>`
				: "";
		return `
			<div class="hat-profile-section">
				<h4>${__("Products")} <span class="text-muted">(${total})</span></h4>
				<div class="hat-profile-products">${cards}</div>
				${more}
			</div>`;
	}

	reviews_html() {
		const esc = frappe.utils.escape_html;
		const reviews = this.data.reviews;
		const body = reviews.length
			? reviews
					.map(
						(r) => `
					<div class="hat-profile-review">
						<div class="hat-profile-review-head">
							${hat.profile.stars(r.rating)}
							<b>${esc(r.hotel_name)}</b>
							<span class="indicator-pill ${r.review_type === "Overall" ? "blue" : "gray"}">${
							r.review_type === "Overall" ? __("Overall review") : __("Order rating")
						}</span>
							<span class="text-muted small">${frappe.datetime.comment_when(r.modified)}</span>
						</div>
						${r.comment ? `<div class="hat-profile-text">${esc(r.comment)}</div>` : ""}
					</div>`
					)
					.join("")
			: `<div class="text-muted hat-profile-empty">${__("No reviews yet.")}</div>`;
		return `
			<div class="hat-profile-section">
				<h4>${__("Reviews from hotels")}</h4>
				<div class="hat-profile-card">${body}</div>
			</div>`;
	}
}
