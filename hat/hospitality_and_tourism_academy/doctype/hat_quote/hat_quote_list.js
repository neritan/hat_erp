frappe.listview_settings["HAT Quote"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		const colours = {
			Draft: "red",
			Submitted: "blue",
			Awarded: "green",
			"Not Awarded": "gray",
			Withdrawn: "gray",
		};
		return [__(doc.status), colours[doc.status], `status,=,${doc.status}`];
	},
};
