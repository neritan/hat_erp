// The hotel's cart: its draft orders, one per distributor, reviewed and placed in one go

frappe.pages["hat-cart"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Cart"),
		single_column: true,
	});
	wrapper.cart = new HATCart(page);
	// namespaced and unbound first, so a re-created page never stacks handlers
	$(document)
		.off("hat:cart-updated.hat-cart")
		.on("hat:cart-updated.hat-cart", () => wrapper.cart.refresh());
};

frappe.pages["hat-cart"].on_page_show = (wrapper) => {
	wrapper.cart.refresh();
};

const CART_API = "hat.cart";

class HATCart {
	constructor(page) {
		this.page = page;
		this.page.set_secondary_action(__("Continue shopping"), () =>
			frappe.set_route("hat-marketplace")
		);
		if (frappe.user.has_role("HAT Staff") || frappe.user.has_role("System Manager")) {
			this.hotel_field = this.page.add_field({
				fieldname: "hotel",
				fieldtype: "Link",
				options: "Customer",
				label: __("Hotel"),
				get_query: () => ({ filters: { customer_group: "Hotel" } }),
				change: () => this.refresh(),
			});
		}
		this.$body = $(`<div class="hat-cart"></div>`).appendTo(page.main);
		this.$body.on("change", "[data-qty]", (e) => {
			const $input = $(e.currentTarget);
			this.update_line($input.attr("data-order"), $input.attr("data-qty"), $input.val());
		});
		this.$body.on("click", "[data-remove]", (e) => {
			const $btn = $(e.currentTarget);
			this.update_line($btn.attr("data-order"), $btn.attr("data-remove"), 0);
		});
		this.$body.on("click", "[data-send-one]", (e) =>
			this.place_order([$(e.currentTarget).attr("data-send-one")])
		);
		this.$body.on("click", "[data-place-order]", () => this.place_order());
	}

	hotel() {
		return this.hotel_field?.get_value() || this.cart?.hotel || null;
	}

	async refresh() {
		if (this.hotel_field && !this.hotel_field.get_value()) {
			this.$body.html(
				`<div class="hat-cart-empty text-muted">${__(
					"Choose a hotel to see its cart."
				)}</div>`
			);
			this.page.clear_primary_action();
			return;
		}
		const { message } = await frappe.call(`${CART_API}.get_cart`, {
			hotel: this.hotel_field?.get_value() || null,
		});
		this.cart = message;
		this.render();
	}

	render() {
		const cart = this.cart;
		this.page.set_title(__("Cart: {0}", [cart.hotel_name]));
		if (!cart.parts.length) {
			this.page.clear_primary_action();
			this.$body.html(`
				<div class="hat-cart-empty">
					<p class="text-muted">${__("Your cart is empty.")}</p>
					<a class="btn btn-primary btn-sm" href="/desk/hat-marketplace">${__("Go to the Marketplace")}</a>
				</div>`);
			return;
		}
		this.page.set_primary_action(__("Place Order ({0})", [this.money(cart.total)]), () =>
			this.place_order()
		);
		this.$body.html(`
			${cart.parts.map((part) => this.part_html(part)).join("")}
			<div class="hat-cart-summary">
				<div>
					<div class="text-muted small">${__("{0} products from {1} distributors", [
						cart.count,
						cart.parts.length,
					])}</div>
					<div class="hat-cart-total">${__("Total")}: ${this.money(cart.total)}</div>
					<div class="text-muted small">${__("Excluding VAT. One order is sent to each distributor.")}</div>
				</div>
				<button class="btn btn-primary" data-place-order>${__("Place Order")}</button>
			</div>`);
	}

	part_html(part) {
		const esc = frappe.utils.escape_html;
		const rating = part.rating
			? `<span class="hat-cart-rating">★ ${(part.rating * 5).toFixed(1)}</span>`
			: "";
		const minimum = part.minimum_order
			? part.missing
				? `<span class="indicator-pill orange">${__("{0} below the minimum order of {1}", [
						this.money(part.missing),
						this.money(part.minimum_order),
				  ])}</span>`
				: `<span class="indicator-pill green">${__("Minimum order reached")}</span>`
			: "";
		const tags = [
			part.partnership
				? `<span class="indicator-pill blue">${__("Partner prices")}</span>`
				: "",
			part.request_type !== "Order"
				? `<span class="indicator-pill gray">${__("Includes price on request")}</span>`
				: "",
		].join(" ");
		return `
			<div class="hat-cart-part">
				<div class="hat-cart-head">
					<div>
						<b>${esc(part.distributor_name)}</b> ${rating}
						<div class="hat-cart-tags">${minimum} ${tags}</div>
					</div>
					<a class="small text-muted" href="/desk/hat-order-request/${encodeURIComponent(part.order)}">${esc(
			part.order
		)}</a>
				</div>
				<table class="table hat-cart-lines">
					<thead><tr>
						<th></th><th>${__("Product")}</th>
						<th class="text-right">${__("Price")}</th>
						<th class="text-right">${__("Quantity")}</th>
						<th class="text-right">${__("Amount")}</th><th></th>
					</tr></thead>
					<tbody>${part.lines.map((line) => this.line_html(part, line)).join("")}</tbody>
				</table>
				<div class="hat-cart-foot">
					<span>${__("Subtotal")}: <b>${this.money(part.total)}</b></span>
					<button class="btn btn-default btn-sm" data-send-one="${esc(part.order)}">${__(
			"Order only this"
		)}</button>
				</div>
			</div>`;
	}

	line_html(part, line) {
		const esc = frappe.utils.escape_html;
		const image = line.image
			? `<img src="${encodeURI(line.image)}" alt="">`
			: `<span>${esc(frappe.get_abbr(line.description || ""))}</span>`;
		const title = line.listing
			? `<a href="/desk/hat-listing/${encodeURIComponent(line.listing)}">${esc(
					line.description
			  )}</a>`
			: esc(line.description);
		const flags = [
			line.unavailable
				? `<span class="indicator-pill red">${__("No longer available")}</span>`
				: "",
			line.minimum_qty > 1
				? `<span class="text-muted small">${__("min. {0}", [line.minimum_qty])}</span>`
				: "",
		].join(" ");
		return `
			<tr>
				<td class="hat-cart-image">${image}</td>
				<td>${title}<div>${flags}</div></td>
				<td class="text-right">${
					line.rate
						? this.money(line.rate)
						: `<span class="text-muted">${__("On request")}</span>`
				}<div class="text-muted small">/ ${esc(__(line.uom || ""))}</div></td>
				<td class="text-right">
					<input type="number" class="form-control input-xs hat-cart-qty" min="0" step="any"
						value="${line.qty}" data-order="${esc(part.order)}" data-qty="${esc(line.name)}">
				</td>
				<td class="text-right">${line.rate ? this.money(line.amount) : "—"}</td>
				<td class="text-right">
					<button class="btn btn-xs btn-link text-muted" title="${__("Remove")}"
						data-order="${esc(part.order)}" data-remove="${esc(line.name)}">
						${frappe.utils.icon("trash-2", "sm")}
					</button>
				</td>
			</tr>`;
	}

	money(value) {
		return format_currency(value || 0, "ALL", 0);
	}

	async update_line(order, line, qty) {
		try {
			await frappe.call({
				method: `${CART_API}.update_line`,
				args: { order, line, qty: flt(qty) },
			});
		} finally {
			this.refresh();
			$(document).trigger("hat:cart-count");
		}
	}

	place_order(orders) {
		const parts = this.cart.parts.filter((p) => !orders || orders.includes(p.order));
		const below = parts.filter((p) => p.missing);
		const dialog = new frappe.ui.Dialog({
			title: orders
				? __("Place order with {0}", [parts[0].distributor_name])
				: __("Place Order"),
			fields: [
				{
					fieldname: "summary",
					fieldtype: "HTML",
					options: `
						<p>${parts
							.map(
								(p) =>
									`${frappe.utils.escape_html(
										p.distributor_name
									)}: <b>${this.money(p.total)}</b>`
							)
							.join("<br>")}</p>
						${
							below.length
								? `<div class="alert alert-warning small">${below
										.map((p) =>
											__("{0} is {1} below its minimum order of {2}.", [
												frappe.utils.escape_html(p.distributor_name),
												this.money(p.missing),
												this.money(p.minimum_order),
											])
										)
										.join("<br>")} ${__(
										"You can still send; the distributor may ask you to add more."
								  )}</div>`
								: ""
						}`,
				},
				{ fieldname: "required_by", fieldtype: "Date", label: __("Delivery needed by") },
				{
					fieldname: "delivery_address",
					fieldtype: "Link",
					options: "Address",
					label: __("Delivery address"),
					get_query: () => ({
						query: "frappe.contacts.doctype.address.address.address_query",
						filters: { link_doctype: "Customer", link_name: this.cart.hotel },
					}),
				},
				{
					fieldname: "notes",
					fieldtype: "Small Text",
					label: __("Notes for the distributors"),
				},
			],
			primary_action_label:
				orders || parts.length === 1
					? __("Place Order")
					: __("Place {0} Orders", [parts.length]),
			primary_action: async (values) => {
				const { message: result } = await frappe.call({
					method: `${CART_API}.place_order`,
					args: { hotel: this.cart.hotel, orders: orders || null, ...values },
					freeze: true,
					freeze_message: __("Placing orders..."),
				});
				dialog.hide();
				this.show_result(result);
				this.refresh();
				$(document).trigger("hat:cart-count");
			},
		});
		dialog.show();
	}

	show_result({ sent, failed, warnings }) {
		const esc = frappe.utils.escape_html;
		const link = (o) =>
			`<a href="/desk/hat-order-request/${encodeURIComponent(o)}">${esc(o)}</a>`;
		frappe.msgprint({
			title: failed.length ? __("Some orders were not placed") : __("Orders placed"),
			indicator: failed.length ? "orange" : "green",
			message: [
				sent.length
					? `<p><b>${__("Placed with the distributors")}</b><br>${sent
							.map(
								(s) =>
									`${link(s.order)}: ${esc(s.distributor_name)}, ${this.money(
										s.total
									)}`
							)
							.join("<br>")}</p>`
					: "",
				failed.length
					? `<p><b>${__("Not placed, still in the cart")}</b><br>${failed
							.map(
								(f) => `${link(f.order)}: ${esc(f.distributor_name)} — ${f.error}`
							)
							.join("<br>")}</p>`
					: "",
				warnings.length
					? `<p class="text-warning">${warnings.map(esc).join("<br>")}</p>`
					: "",
			].join(""),
		});
	}
}

frappe.dom.set_style(`
	.hat-cart { padding: var(--padding-md) 0; display: flex; flex-direction: column; gap: var(--margin-md); }
	.hat-cart-empty { padding: var(--padding-xl) 0; text-align: center; }
	.hat-cart-part {
		background: var(--card-bg);
		border: 1px solid var(--border-color);
		border-radius: var(--border-radius-lg);
		padding: var(--padding-md);
	}
	.hat-cart-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--padding-sm); }
	.hat-cart-tags { margin-top: 4px; display: flex; flex-wrap: wrap; gap: 4px; }
	.hat-cart-rating { color: var(--yellow-600, #d97706); font-size: var(--text-sm); }
	.hat-cart-lines { margin: var(--margin-sm) 0; }
	.hat-cart-lines td { vertical-align: middle; }
	.hat-cart-image { width: 44px; }
	.hat-cart-image img, .hat-cart-image span {
		width: 36px; height: 36px; border-radius: var(--border-radius);
		display: flex; align-items: center; justify-content: center;
		background: var(--subtle-fg); color: var(--text-muted); font-size: var(--text-xs);
		object-fit: cover;
	}
	.hat-cart-qty { width: 90px; margin-left: auto; text-align: right; }
	.hat-cart-foot { display: flex; justify-content: space-between; align-items: center; }
	.hat-cart-summary {
		display: flex; justify-content: space-between; align-items: center; gap: var(--padding-md);
		background: var(--card-bg);
		border: 1px solid var(--border-color);
		border-radius: var(--border-radius-lg);
		padding: var(--padding-md);
		position: sticky; bottom: var(--padding-sm);
	}
	.hat-cart-total { font-size: var(--text-xl); font-weight: 600; color: var(--heading-color); }
`);
