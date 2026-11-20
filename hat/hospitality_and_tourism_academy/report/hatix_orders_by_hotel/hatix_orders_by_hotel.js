frappe.query_reports["Hatix Orders by Hotel"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "hotel",
			label: __("Hotel"),
			fieldtype: "Link",
			options: "Customer",
			get_query: () => ({ filters: { customer_group: "Hotel" } }),
		},
		{
			fieldname: "distributor",
			label: __("Distributor"),
			fieldtype: "Link",
			options: "Supplier",
			get_query: () => ({ filters: { supplier_group: "Distributor" } }),
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: [
				"",
				"Sent",
				"Quoted",
				"Accepted",
				"Delivered",
				"Completed",
				"Rejected",
				"Cancelled",
			],
		},
	],
};
