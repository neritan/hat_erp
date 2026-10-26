// Copyright (c) 2026, HAT and contributors
// For license information, please see license.txt

frappe.ui.form.on("HAT Listing", {
	setup(frm) {
		frm.set_query("item", () => ({ filters: { disabled: 0, has_variants: 0 } }));
		frm.set_query("distributor", () => ({ filters: { supplier_group: "Distributor" } }));
	},

	refresh(frm) {
		if (!frm.doc.item) {
			frm.add_custom_button(__("Create Product"), () => create_product(frm));
		}
		if (frm.is_new() || !frm.doc.published) return;

		if (frm.doc.availability === "Available" && hat.marketplace.can_order()) {
			frm.add_custom_button(__("Add to Cart"), () => hat.marketplace.add_to_order(frm.doc));
			frm.change_custom_button_type(__("Add to Cart"), null, "primary");
		}
		frappe
			.call(
				"hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing.get_price_for_hotel",
				{ listing: frm.doc.name }
			)
			.then(({ message }) => {
				if (message.hotel) {
					frm.set_intro(hat.marketplace.price_html(message), "blue");
				}
			});
	},
});

// A product missing from the catalogue: add it (or reuse the one with the same name) and select it
function create_product(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Create Product"),
		fields: [
			{
				fieldname: "item_name",
				fieldtype: "Data",
				label: __("Product Name"),
				reqd: 1,
				description: __(
					"Include brand and pack size, e.g. Birra Tirana 0.33 L, crate of 24"
				),
			},
			{
				fieldname: "item_group",
				fieldtype: "Link",
				label: __("Category"),
				options: "Item Group",
				reqd: 1,
				get_query: () => ({ filters: { is_group: 0 } }),
			},
			{ fieldname: "uom", fieldtype: "Link", label: __("Unit"), options: "UOM", reqd: 1 },
		],
		primary_action_label: __("Create"),
		primary_action: async (values) => {
			const { message: item } = await frappe.call({
				method: "hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing.create_product",
				args: values,
				freeze: true,
			});
			dialog.hide();
			frm.set_value("item", item);
		},
	});
	dialog.show();
}
