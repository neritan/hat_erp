frappe.provide("hat.marketplace");

const LISTING_API = "hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing";

// Ask for quantity (and hotel, for HAT staff) and add a listing to the hotel's draft order request.
// `qty` pre-fills the quantity, e.g. from the marketplace's compact list.
hat.marketplace.add_to_order = async (listing, hotel, qty) => {
	const { message: price } = await frappe.call(`${LISTING_API}.get_price_for_hotel`, {
		listing: listing.name,
		hotel,
	});
	const dialog = new frappe.ui.Dialog({
		title: __("Add {0} to Cart", [listing.title]),
		fields: [
			{
				fieldname: "hotel",
				fieldtype: "Link",
				label: __("Hotel"),
				options: "Customer",
				reqd: 1,
				default: price.hotel,
				hidden: price.hotel ? 1 : 0,
				get_query: () => ({ filters: { customer_group: "Hotel" } }),
			},
			{
				fieldname: "qty",
				fieldtype: "Float",
				label: __("Quantity ({0})", [__(listing.uom)]),
				reqd: 1,
				default: qty || listing.minimum_qty || 1,
				description:
					listing.minimum_qty > 1 ? __("Minimum order: {0}", [listing.minimum_qty]) : "",
				onchange: () => {
					if (!price.tiers || !price.tiers.length) return;
					dialog.fields_dict.price.$wrapper.html(
						hat.marketplace.price_html(price, dialog.get_value("qty"), listing.uom)
					);
				},
			},
			{
				fieldname: "price",
				fieldtype: "HTML",
				options: hat.marketplace.price_html(
					price,
					price.tiers && price.tiers.length
						? qty || listing.minimum_qty || 1
						: undefined,
					listing.uom
				),
			},
		],
		primary_action_label: __("Add to Cart"),
		primary_action: async ({ hotel, qty }) => {
			const { message: order } = await frappe.call({
				method: `${LISTING_API}.add_to_order`,
				args: { listing: listing.name, qty, hotel },
				freeze: true,
			});
			dialog.hide();
			frappe.show_alert({
				message: __("Added to the cart ({0}). {1}", [
					`<a href="/desk/hat-order-request/${order}">${order}</a>`,
					`<a href="/desk/hat-cart">${__("View cart")}</a>`,
				]),
				indicator: "green",
			});
			$(document).trigger("hat:cart-count");
			$(document).trigger("hat:cart-updated");
		},
	});
	dialog.show();
};

// Price on Quantity: the range a quantity falls in (the whole quantity gets that range's price)
hat.marketplace.tier_for = (tiers, qty) => {
	let found = tiers[0];
	for (const tier of tiers) {
		if (flt(qty) >= tier.from_qty) found = tier;
	}
	return found;
};

// "1–9", "10–49", "50+" for each range
hat.marketplace.tier_label = (tiers, i) => {
	const next = tiers[i + 1];
	const from = format_number(tiers[i].from_qty, null, 0);
	if (!next) return `${from}+`;
	const to = next.from_qty - 1 >= tiers[i].from_qty ? next.from_qty - 1 : next.from_qty;
	return to === tiers[i].from_qty ? from : `${from}–${format_number(to, null, 0)}`;
};

hat.marketplace.tiers_html = (tiers, uom, qty) => {
	const current = qty === undefined ? null : hat.marketplace.tier_for(tiers, qty);
	const partner = tiers.some((t) => t.rate < t.price);
	const rows = tiers
		.map((tier, i) => {
			const active = current === tier ? ' class="hat-tier-active"' : "";
			const price = partner
				? `<b>${format_currency(
						tier.rate,
						"ALL"
				  )}</b> <s class="text-muted">${format_currency(tier.price, "ALL")}</s>`
				: `<b>${format_currency(tier.rate, "ALL")}</b>`;
			return `<tr${active}><td>${hat.marketplace.tier_label(
				tiers,
				i
			)} ${frappe.utils.escape_html(
				__(uom || "")
			)}</td><td class="text-right">${price}</td></tr>`;
		})
		.join("");
	return `<table class="table table-sm hat-tiers"><thead><tr><th>${__("Quantity")}</th>
		<th class="text-right">${partner ? __("Your partner price / unit") : __("Price / unit")}</th>
		</tr></thead><tbody>${rows}</tbody></table>`;
};

hat.marketplace.price_html = (price, qty, uom) => {
	if (price.rate === null || price.rate === undefined) {
		return `<p class="text-muted">${__(
			"Price on request: the distributor will send you a quote."
		)}</p>`;
	}
	if (price.tiers && price.tiers.length) {
		let html = hat.marketplace.tiers_html(price.tiers, uom, qty);
		if (qty !== undefined && flt(qty) > 0) {
			const rate = hat.marketplace.tier_for(price.tiers, qty).rate;
			html += `<p>${__("{0} × {1} = {2}", [
				format_number(qty),
				`<b>${format_currency(rate, "ALL")}</b>`,
				`<b>${format_currency(rate * flt(qty), "ALL")}</b>`,
			])}</p>`;
		}
		return html;
	}
	const rate = format_currency(price.rate, "ALL");
	if (price.rate < price.public_price) {
		return `<p>${__("Your partner price: {0}", [`<b>${rate}</b>`])}
			<span class="text-muted">(${__("public price {0}", [
				format_currency(price.public_price, "ALL"),
			])})</span></p>`;
	}
	return `<p>${__("Price: {0}", [`<b>${rate}</b>`])}</p>`;
};

hat.marketplace.can_order = () => frappe.model.can_create("HAT Order Request");

frappe.dom.set_style(`
	.hat-tiers { margin-bottom: var(--margin-sm); }
	.hat-tiers td, .hat-tiers th { padding: 2px 6px; }
	.hat-tiers .hat-tier-active td { background: var(--bg-green); }
`);

// Add a product to the hotel's draft quote request, which all matching distributors see once published
hat.marketplace.request_quotes = (product, hotel) => {
	const dialog = new frappe.ui.Dialog({
		title: __("Request quotes: {0}", [product.item_name]),
		fields: [
			{
				fieldname: "hotel",
				fieldtype: "Link",
				label: __("Hotel"),
				options: "Customer",
				reqd: 1,
				default: hotel,
				hidden: hotel ? 1 : 0,
				get_query: () => ({ filters: { customer_group: "Hotel" } }),
			},
			{ fieldname: "qty", fieldtype: "Float", label: __("Quantity"), reqd: 1, default: 1 },
		],
		primary_action_label: __("Add to Quote Request"),
		primary_action: async ({ hotel, qty }) => {
			const { message: request } = await frappe.call({
				method: "hat.hospitality_and_tourism_academy.doctype.hat_quote_request.hat_quote_request.add_to_quote_request",
				args: { item: product.name, qty, hotel },
				freeze: true,
			});
			dialog.hide();
			frappe.show_alert({
				message: __("Added to {0}. Publish it when your list is ready.", [
					`<a href="/desk/hat-quote-request/${request}">${request}</a>`,
				]),
				indicator: "green",
			});
		},
	});
	dialog.show();
};

// Sidebar header: "Hatix" on the first line, "Marketplace" under it. The sidebar is named "Hatix"
// (in Frappe 17 its name is the shell in desk URLs, /desk/hatix/...), so the second line is set
// here. Frappe 16 already draws a second line, the app title "Hatix Marketplace", which is
// replaced; Frappe 17 draws none, so one is added in Frappe's own header-subtitle style.
if (frappe.ui.SidebarHeader) {
	const HATIX_SIDEBAR = "Hatix";
	// Frappe 17 names the sidebar on screen in sidebar_data.name, Frappe 16 in sidebar_title.
	const is_hatix = (sidebar) =>
		[sidebar?.sidebar_data?.name, sidebar?.sidebar_title].includes(HATIX_SIDEBAR);
	const show_marketplace_line = (header) => {
		const $container = header.wrapper?.find(".title-container");
		if (!$container?.length) return;
		$container.find(".hat-header-subtitle").remove();
		if (!is_hatix(header.sidebar)) return;
		const $own = $container.find(".header-subtitle");
		if ($own.length) {
			$own.text(__("Marketplace"));
		} else {
			$("<div class='header-subtitle hat-header-subtitle'></div>")
				.text(__("Marketplace"))
				.appendTo($container);
		}
	};
	for (const method of ["make", "refresh"]) {
		const original = frappe.ui.SidebarHeader.prototype[method];
		if (!original) continue;
		frappe.ui.SidebarHeader.prototype[method] = function (...args) {
			const result = original.apply(this, args);
			show_marketplace_line(this);
			return result;
		};
	}
}

// Review dialog: a hotel rates one completed order, or reviews a distributor overall (no order).
// Opens the hotel's existing review when there is one, so saving edits it instead of adding another.
frappe.provide("hat.reviews");

hat.reviews.open = async ({ distributor, order_request, hotel, on_saved } = {}) => {
	const { message: review } = await frappe.call("hat.reviews.get_review", {
		distributor,
		order_request: order_request || null,
		hotel: hotel || null,
	});
	const dialog = new frappe.ui.Dialog({
		title: order_request
			? __("Rate order {0}", [order_request])
			: __("Review {0}", [review.distributor_name || review.distributor]),
		fields: [
			{
				fieldname: "rating",
				fieldtype: "Rating",
				label: __("Overall"),
				reqd: 1,
				default: review.rating || 0,
			},
			{ fieldtype: "Section Break" },
			{
				fieldname: "quality",
				fieldtype: "Rating",
				label: __("Product quality"),
				default: review.quality || 0,
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "delivery",
				fieldtype: "Rating",
				label: __("Delivery"),
				default: review.delivery || 0,
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "communication",
				fieldtype: "Rating",
				label: __("Communication"),
				default: review.communication || 0,
			},
			{ fieldtype: "Section Break" },
			{
				fieldname: "comment",
				fieldtype: "Small Text",
				label: __("Comment"),
				default: review.comment || "",
			},
		],
		primary_action_label: review.name ? __("Update review") : __("Save review"),
		primary_action: async (values) => {
			if (!values.rating) {
				frappe.msgprint(__("Give at least one star"));
				return;
			}
			await frappe.call("hat.reviews.save_review", {
				...values,
				distributor: review.distributor,
				order_request: order_request || null,
				hotel: review.hotel,
			});
			dialog.hide();
			frappe.show_alert({ message: __("Thank you for your review"), indicator: "green" });
			on_saved?.();
		},
	});
	dialog.show();
};

// Completed order requests: the hotel rates the order from the form.
frappe.ui.form.on("HAT Order Request", {
	refresh(frm) {
		if (
			frm.doc.status !== "Completed" ||
			frm.is_new() ||
			!frappe.model.can_create("HAT Distributor Rating")
		) {
			return;
		}
		frm.add_custom_button(__("Rate this order"), () =>
			hat.reviews.open({
				distributor: frm.doc.distributor,
				order_request: frm.doc.name,
				hotel: frm.doc.hotel,
			})
		);
	},
});

// User form: a hotel or distributor user belongs to one structure, chosen here (see hat/users.py).
// HAT staff and System Managers work across all of them and get no structure.
frappe.provide("hat.users");

hat.users.STRUCTURE_ROLES = ["Hotel", "Distributor"];
hat.users.FULL_DESK_ROLES = ["Administrator", "System Manager", "HAT Staff"];

// Whether `doc` (a User) needs a structure; with `role`, whether it needs that one.
hat.users.needs_structure = (doc, role) => {
	const roles = (doc.roles || []).map((r) => r.role);
	if (roles.some((r) => hat.users.FULL_DESK_ROLES.includes(r))) return false;
	const held = hat.users.STRUCTURE_ROLES.filter((r) => roles.includes(r));
	return role ? held.includes(role) : held.length > 0;
};

frappe.ui.form.on("User", {
	setup(frm) {
		frm.set_query("hat_hotel", () => ({ filters: { customer_group: "Hotel" } }));
		frm.set_query("hat_distributor", () => ({ filters: { supplier_group: "Distributor" } }));
	},
	refresh(frm) {
		// Ticking a role updates doc.roles; show or hide the structure fields right away.
		$(frm.fields_dict.roles_html?.wrapper)
			.off("change.hat-structure")
			.on("change.hat-structure", "input[type=checkbox]", () =>
				setTimeout(() => frm.layout.refresh_dependency())
			);
	},
});

// Read-only profile pages: hotels see a distributor (hat-distributor), distributors see a hotel
// (hat-hotel). Shared pieces and styles, in the look of the product page.
frappe.provide("hat.profile");

hat.profile.STAFF_ROLES = ["HAT Staff", "System Manager", "Administrator"];
hat.profile.is_only = (role) =>
	frappe.user.has_role(role) && !hat.profile.STAFF_ROLES.some((r) => frappe.user.has_role(r));

// A Rating value (0–1) as stars out of 5
hat.profile.stars = (value, count) => {
	if (!value) return `<span class="text-muted">${__("No ratings yet")}</span>`;
	const suffix =
		count === undefined
			? ""
			: ` <span class="text-muted small">(${
					count === 1 ? __("1 rating") : __("{0} ratings", [count])
			  })</span>`;
	return `<span class="hat-profile-stars">★ ${(value * 5).toFixed(1)}</span>${suffix}`;
};

hat.profile.facts = (rows) =>
	rows
		.map(
			([label, value]) =>
				`<div class="hat-profile-fact"><span class="text-muted">${label}</span><span>${value}</span></div>`
		)
		.join("");

hat.profile.stat = (label, value) =>
	`<div class="hat-profile-stat"><div class="text-muted small">${label}</div><div class="hat-profile-stat-value">${value}</div></div>`;

hat.profile.contact = (doc) => {
	const esc = frappe.utils.escape_html;
	const links = [
		doc.email_id
			? `<a href="mailto:${esc(doc.email_id)}">${frappe.utils.icon("mail", "xs")} ${esc(
					doc.email_id
			  )}</a>`
			: "",
		doc.mobile_no
			? `<a href="tel:${esc(doc.mobile_no)}">${frappe.utils.icon("phone", "xs")} ${esc(
					doc.mobile_no
			  )}</a>`
			: "",
		doc.website && /^https?:\/\//i.test(doc.website)
			? `<a href="${esc(doc.website)}" target="_blank" rel="noopener noreferrer">${esc(
					doc.website
			  )}</a>`
			: "",
	].filter(Boolean);
	return links.length ? `<div class="hat-profile-contact">${links.join("")}</div>` : "";
};

hat.profile.status_color = (status) =>
	({
		Completed: "green",
		Delivered: "green",
		Accepted: "blue",
		Sent: "orange",
		Quoted: "orange",
		Rejected: "red",
		Cancelled: "red",
	}[status] || "gray");

// Hotels open a distributor, and distributors a hotel, as the read-only page instead of the form.
// The history entry is replaced so Back does not bounce into the form again.
frappe.router?.on?.("change", () => {
	const [view, doctype, name] = frappe.get_route();
	if (view !== "Form" || !name || name.startsWith("new-")) return;
	let page = null;
	if (
		doctype === "Supplier" &&
		hat.profile.is_only("Hotel") &&
		!frappe.user.has_role("Distributor")
	) {
		page = "hat-distributor";
	} else if (
		doctype === "Customer" &&
		hat.profile.is_only("Distributor") &&
		!frappe.user.has_role("Hotel")
	) {
		page = "hat-hotel";
	}
	if (!page) return;
	frappe.route_flags.replace_route = true;
	frappe.set_route(page, name);
});

// Read-only hotel and distributor views, shared by the hat-hotel / hat-distributor pages and the
// "Hotel Profile" / "Distributor Profile" tabs of the Customer / Supplier forms.
hat.profile.HotelView = class HotelView {
	constructor($body) {
		this.$body = $body;
	}

	// Renders the hotel; returns its data, or null when it cannot be shown.
	async load(name) {
		this.$body.html(`<div class="text-muted hat-profile-loading">${__("Loading…")}</div>`);
		try {
			const { message } = await frappe.call({
				method: "hat.hospitality_and_tourism_academy.page.hat_hotel.hat_hotel.get_hotel",
				args: { hotel: name },
			});
			this.data = message;
		} catch {
			this.$body.html(
				`<div class="text-muted hat-profile-loading">${__(
					"This hotel is not available."
				)}</div>`
			);
			return null;
		}
		this.$body.html(
			[this.header_html(), this.dealings_html(), this.quote_requests_html()].join("")
		);
		return this.data;
	}

	header_html() {
		const esc = frappe.utils.escape_html;
		const h = this.data.hotel;
		const logo = h.image
			? `<img src="${encodeURI(h.image)}" alt="${esc(h.customer_name)}">`
			: `<span>${esc(frappe.get_abbr(h.customer_name))}</span>`;
		const stars = h.hat_star_rating ? "★".repeat(parseInt(h.hat_star_rating)) : "";
		const place = [h.hat_city, h.territory].filter(Boolean).map(esc).join(", ");
		const map =
			h.hat_latitude && h.hat_longitude
				? `<a href="https://www.openstreetmap.org/?mlat=${h.hat_latitude}&mlon=${
						h.hat_longitude
				  }#map=16/${h.hat_latitude}/${
						h.hat_longitude
				  }" target="_blank" rel="noopener noreferrer">${frappe.utils.icon(
						"map-pin",
						"xs"
				  )} ${__("Show on map")}</a>`
				: "";
		const facts = [
			[__("Property type"), h.hat_hotel_type ? esc(__(h.hat_hotel_type)) : "–"],
			[__("Stars"), stars ? `<span class="hat-profile-stars">${stars}</span>` : "–"],
			[__("Rooms"), h.hat_number_of_rooms || "–"],
			[__("Region"), h.territory ? esc(h.territory) : "–"],
		];
		return `
			<div class="hat-profile-card hat-profile-head">
				<div class="hat-profile-logo">${logo}</div>
				<div class="hat-profile-info">
					<h2 class="hat-profile-title">${esc(h.customer_name)} ${
			stars ? `<span class="hat-profile-stars">${stars}</span>` : ""
		}</h2>
					<div class="text-muted">${place}</div>
					${
						h.primary_address
							? `<div class="hat-profile-text hat-profile-address">${esc(
									h.primary_address.replace(/<br\s*\/?>/gi, "\n")
							  )}</div>`
							: ""
					}
					${map ? `<div class="small">${map}</div>` : ""}
				</div>
				<div class="hat-profile-side">
					${hat.profile.facts(facts)}
					${hat.profile.contact(h)}
				</div>
			</div>`;
	}

	dealings_html() {
		const esc = frappe.utils.escape_html;
		const d = this.data.dealings;
		const rows = d.recent
			.map(
				(o) => `
				<tr>
					<td><a href="/desk/hat-order-request/${encodeURIComponent(o.name)}">${esc(o.name)}</a></td>
					<td>${frappe.datetime.str_to_user(o.transaction_date)}</td>
					<td>${esc(o.distributor_name || "")}</td>
					<td><span class="indicator-pill ${hat.profile.status_color(o.status)}">${esc(
					__(o.status)
				)}</span></td>
					<td class="text-right">${format_currency(o.total_amount, "ALL", 0)}</td>
				</tr>`
			)
			.join("");
		return `
			<div class="hat-profile-section">
				<h4>${__("Order requests")}</h4>
				<div class="hat-profile-card hat-profile-stats">
					${hat.profile.stat(__("Order requests"), d.orders)}
					${hat.profile.stat(__("Open"), d.open)}
					${hat.profile.stat(__("Completed"), d.completed)}
					${hat.profile.stat(__("Ordered"), format_currency(d.ordered, "ALL", 0))}
					${hat.profile.stat(
						__("Last request"),
						d.last_order ? frappe.datetime.str_to_user(d.last_order) : "–"
					)}
				</div>
				${
					rows
						? `<div class="hat-profile-card hat-profile-table-wrap">
							<table class="table hat-profile-table">
								<thead><tr>
									<th>${__("Order Request")}</th><th>${__("Date")}</th><th>${__("Distributor")}</th>
									<th>${__("Status")}</th><th class="text-right">${__("Total")}</th>
								</tr></thead>
								<tbody>${rows}</tbody>
							</table>
						</div>`
						: ""
				}
			</div>`;
	}

	quote_requests_html() {
		const esc = frappe.utils.escape_html;
		const requests = this.data.open_quote_requests;
		if (!requests.length) return "";
		const rows = requests
			.map(
				(r) => `
				<tr>
					<td><a href="/desk/hat-quote-request/${encodeURIComponent(r.name)}">${esc(
					r.title || r.name
				)}</a></td>
					<td>${r.quote_deadline ? frappe.datetime.str_to_user(r.quote_deadline) : "–"}</td>
					<td>${r.required_by ? frappe.datetime.str_to_user(r.required_by) : "–"}</td>
				</tr>`
			)
			.join("");
		return `
			<div class="hat-profile-section">
				<h4>${__("Open quote requests")}</h4>
				<div class="hat-profile-card hat-profile-table-wrap">
					<table class="table hat-profile-table">
						<thead><tr><th>${__("Request")}</th><th>${__("Quotes due by")}</th><th>${__(
			"Needed by"
		)}</th></tr></thead>
						<tbody>${rows}</tbody>
					</table>
				</div>
			</div>`;
	}
};

hat.profile.DistributorView = class DistributorView {
	constructor($body) {
		this.$body = $body;
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

	// Renders the distributor; returns its data, or null when it cannot be shown.
	async load(name) {
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
			return null;
		}
		this.$body.html(
			[
				this.header_html(),
				this.with_hotel_html(),
				this.products_html(),
				this.reviews_html(),
			].join("")
		);
		return this.data;
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
};

// Customer (Hotel) and Supplier (Distributor) forms: a read-only profile tab, filled when the form
// loads. The tab and its HTML field are custom fields (see install.get_custom_fields).
hat.profile.render_tab = (frm, View) => {
	const field = frm.get_field("hat_profile_html");
	if (!field || frm.is_new()) return;
	const $body = $(`<div class="hat-profile hat-profile-in-form"></div>`);
	field.$wrapper.empty().append($body);
	new View($body).load(frm.doc.name);
};

frappe.ui.form.on("Customer", {
	refresh(frm) {
		if (frm.doc.customer_group === "Hotel") hat.profile.render_tab(frm, hat.profile.HotelView);
	},
});

frappe.ui.form.on("Supplier", {
	refresh(frm) {
		if (frm.doc.supplier_group === "Distributor")
			hat.profile.render_tab(frm, hat.profile.DistributorView);
	},
});

frappe.dom.set_style(`
	.hat-profile { padding: var(--padding-md) 0 var(--padding-xl); display: flex; flex-direction: column; gap: var(--margin-lg); }
	.hat-profile-in-form { padding-top: 0; }
	.hat-profile-loading, .hat-profile-empty { padding: var(--padding-lg); }
	.hat-profile-card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: var(--border-radius-lg); overflow: hidden; }
	.hat-profile-section h4 { margin-bottom: var(--margin-sm); }
	.hat-profile-stars { color: var(--yellow-600, #d97706); }

	.hat-profile-head { display: grid; grid-template-columns: 160px minmax(0, 1fr) minmax(240px, 320px); }
	.hat-profile-logo { background: #fff; display: flex; align-items: center; justify-content: center; padding: var(--padding-md); border-right: 1px solid var(--border-color); color: var(--text-muted); font-size: 2rem; font-weight: 600; min-height: 160px; }
	.hat-profile-logo img { max-width: 100%; max-height: 140px; object-fit: contain; }
	.hat-profile-info { padding: var(--padding-lg); display: flex; flex-direction: column; gap: var(--padding-xs); min-width: 0; }
	.hat-profile-title { margin: 0; font-size: var(--text-2xl); }
	.hat-profile-pills, .hat-profile-tags { display: flex; flex-wrap: wrap; gap: var(--padding-xs); }
	.hat-profile-tag { font-size: var(--text-sm); padding: 2px 8px; border-radius: var(--border-radius-full, 999px); background: var(--subtle-fg, var(--gray-100)); }
	.hat-profile-text { color: var(--text-color); line-height: 1.6; max-width: 70ch; }
	.hat-profile-address { white-space: pre-line; }
	.hat-profile-actions { display: flex; flex-wrap: wrap; gap: var(--padding-sm); margin-top: var(--margin-sm); }
	.hat-profile-side { padding: var(--padding-lg); border-left: 1px solid var(--border-color); display: flex; flex-direction: column; gap: var(--padding-xs); }
	.hat-profile-fact { display: flex; justify-content: space-between; gap: var(--padding-md); font-size: var(--text-sm); }
	.hat-profile-fact span:last-child { text-align: right; }
	.hat-profile-contact { display: flex; flex-direction: column; gap: 2px; font-size: var(--text-sm); padding-top: var(--padding-xs); margin-top: var(--padding-xs); border-top: 1px solid var(--border-color); word-break: break-word; }

	.hat-profile-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); }
	.hat-profile-stat { padding: var(--padding-md); border-right: 1px solid var(--border-color); }
	.hat-profile-stat:last-child { border-right: 0; }
	.hat-profile-stat-value { font-size: var(--text-lg); font-weight: 600; color: var(--heading-color); }
	.hat-profile-rate { display: flex; flex-wrap: wrap; align-items: center; gap: var(--padding-xs); margin-top: var(--margin-sm); }

	.hat-profile-products { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: var(--margin-md); margin-bottom: var(--margin-sm); }
	.hat-profile-product { padding: var(--padding-sm); display: flex; flex-direction: column; gap: 2px; color: inherit; text-decoration: none; }
	.hat-profile-product:hover { border-color: var(--gray-400); text-decoration: none; }
	.hat-profile-product-photo { height: 110px; background: #fff; display: flex; align-items: center; justify-content: center; margin-bottom: var(--margin-xs); color: var(--text-muted); font-weight: 600; }
	.hat-profile-product-photo img { max-width: 100%; max-height: 100%; object-fit: contain; }
	.hat-profile-product-name { font-weight: 600; color: var(--heading-color); line-height: 1.3; }

	.hat-profile-review { padding: var(--padding-md); border-bottom: 1px solid var(--border-color); display: flex; flex-direction: column; gap: var(--padding-xs); }
	.hat-profile-review:last-child { border-bottom: 0; }
	.hat-profile-review-head { display: flex; flex-wrap: wrap; align-items: center; gap: var(--padding-sm); }

	.hat-profile-table-wrap { overflow-x: auto; margin-top: var(--margin-sm); }
	.hat-profile-table { margin: 0; min-width: 560px; }
	.hat-profile-table th { font-weight: 500; color: var(--text-muted); font-size: var(--text-sm); white-space: nowrap; }
	.hat-profile-table td, .hat-profile-table th { padding: var(--padding-sm) var(--padding-md); vertical-align: middle; }

	@media (max-width: 900px) {
		.hat-profile-head { grid-template-columns: 1fr; }
		.hat-profile-logo { border-right: 0; border-bottom: 1px solid var(--border-color); min-height: 120px; }
		.hat-profile-side { border-left: 0; border-top: 1px solid var(--border-color); }
	}
`);
