frappe.listview_settings["HAT Quote Request"] = {
	add_fields: ["status", "quote_count"],
	get_indicator(doc) {
		const colours = {
			Draft: "red",
			Open: "blue",
			Closed: "orange",
			Awarded: "green",
			Cancelled: "gray",
		};
		return [__(doc.status), colours[doc.status], `status,=,${doc.status}`];
	},
};
