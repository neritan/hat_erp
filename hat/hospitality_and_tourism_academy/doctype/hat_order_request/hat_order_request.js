// Copyright (c) 2026, HAT and contributors
// For license information, please see license.txt

frappe.ui.form.on("HAT Order Request", {
	setup(frm) {
		frm.set_query("listing", "items", () => ({
			filters: { distributor: frm.doc.distributor, published: 1 },
		}));
	},
});

frappe.ui.form.on("HAT Order Request Item", {
	async listing(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.listing) return;
		const listing = await frappe.db.get_doc("HAT Listing", row.listing);
		const { message: price } = await frappe.call(
			"hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing.get_price_for_hotel",
			{ listing: row.listing, hotel: frm.doc.hotel }
		);
		frappe.model.set_value(cdt, cdn, {
			item_group: listing.item_group,
			item: listing.item,
			description: listing.title,
			uom: listing.uom,
			qty: Math.max(row.qty || 0, listing.minimum_qty || 1),
			rate: price.rate,
		});
	},
});
