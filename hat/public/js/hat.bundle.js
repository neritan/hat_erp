frappe.provide("hat.marketplace");

const LISTING_API = "hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing";

// Ask for quantity (and hotel, for HAT staff) and add a listing to the hotel's draft order request
hat.marketplace.add_to_order = async (listing, hotel) => {
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
				default: listing.minimum_qty || 1,
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
					price.tiers && price.tiers.length ? listing.minimum_qty || 1 : undefined,
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
