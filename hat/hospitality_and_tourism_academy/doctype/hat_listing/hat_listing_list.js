frappe.listview_settings["HAT Listing"] = {
	add_fields: ["availability", "published", "minimum_qty", "uom", "price_type", "image"],
	get_indicator(doc) {
		if (!doc.published) return [__("Unpublished"), "gray", "published,=,0"];
		if (doc.availability === "Out of Stock") {
			return [__("Out of Stock"), "red", "availability,=,Out of Stock"];
		}
		return [__("Available"), "green", "availability,=,Available"];
	},
	onload(listview) {
		if (!frappe.user.has_role("Hotel")) return;
		// Optional: coverage never hides listings unless the hotel asks for it
		listview.page.add_inner_button(__("Delivers to my region"), async () => {
			const { message: distributors } = await frappe.call(
				"hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing.get_distributors_for_region"
			);
			listview.filter_area.add([["HAT Listing", "distributor", "in", distributors]]);
		});
	},
	button: {
		show: (doc) =>
			doc.published && doc.availability === "Available" && hat.marketplace.can_order(),
		get_label: () => __("Add to Cart"),
		get_description: (doc) => __("Add {0} to your cart", [doc.title]),
		action: (doc) => hat.marketplace.add_to_order(doc),
	},
};
