// A hotel as distributors see it, read-only: the property, where it is, how to reach it, and what
// the distributor has done with it. Distributors land here instead of the Customer form.
// Route: /desk/hat-hotel/<customer>

frappe.pages["hat-hotel"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Hotel"),
		single_column: true,
	});
	wrapper.hotel_page = new HATHotelPage(page);
};

frappe.pages["hat-hotel"].on_page_show = (wrapper) => {
	wrapper.hotel_page.load(frappe.get_route()[1]);
};

class HATHotelPage {
	constructor(page) {
		this.page = page;
		this.$body = $(`<div class="hat-profile"></div>`).appendTo(page.main);
	}

	async load(name) {
		if (!name) {
			frappe.set_route("List", "Customer");
			return;
		}
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
					"You can see a hotel once you have an order request, quote or partnership with it."
				)}</div>`
			);
			return;
		}
		this.page.set_title(this.data.hotel.customer_name);
		this.$body.html(
			[this.header_html(), this.dealings_html(), this.quote_requests_html()].join("")
		);
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
}
