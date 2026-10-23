frappe.provide("hat.marketplace");

const LISTING_API = "hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing";

// Ask for quantity (and hotel, for HAT staff) and add a listing to the hotel's draft order request
hat.marketplace.add_to_order = async (listing, hotel) => {
	const { message: price } = await frappe.call(`${LISTING_API}.get_price_for_hotel`, {
		listing: listing.name,
		hotel,
	});
	const dialog = new frappe.ui.Dialog({
		title: __("Add {0} to Order", [listing.title]),
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
			},
			{
				fieldname: "price",
				fieldtype: "HTML",
				options: hat.marketplace.price_html(price),
			},
		],
		primary_action_label: __("Add to Order"),
		primary_action: async ({ hotel, qty }) => {
			const { message: order } = await frappe.call({
				method: `${LISTING_API}.add_to_order`,
				args: { listing: listing.name, qty, hotel },
				freeze: true,
			});
			dialog.hide();
			frappe.show_alert({
				message: __("Added to {0}", [
					`<a href="/desk/hat-order-request/${order}">${order}</a>`,
				]),
				indicator: "green",
			});
		},
	});
	dialog.show();
};

hat.marketplace.price_html = (price) => {
	if (price.rate === null || price.rate === undefined) {
		return `<p class="text-muted">${__(
			"Price on request: the distributor will send you a quote."
		)}</p>`;
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
