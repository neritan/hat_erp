frappe.query_reports["Hatix Product Catalogue"] = {
	filters: [
		{
			fieldname: "distributor",
			label: __("Distributor"),
			fieldtype: "Link",
			options: "Supplier",
			get_query: () => ({ filters: { supplier_group: "Distributor" } }),
		},
		{
			fieldname: "item_group",
			label: __("Category"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "availability",
			label: __("Availability"),
			fieldtype: "Select",
			options: ["", "Available", "Out of Stock"],
		},
		{
			fieldname: "price_type",
			label: __("Price Type"),
			fieldtype: "Select",
			options: ["", "Fixed Price", "Price on Request", "Price on Quantity"],
		},
		{
			fieldname: "published",
			label: __("Published"),
			fieldtype: "Select",
			options: ["", "Yes", "No"],
		},
		{
			fieldname: "missing_image",
			label: __("Only Without Image"),
			fieldtype: "Check",
		},
	],
};
