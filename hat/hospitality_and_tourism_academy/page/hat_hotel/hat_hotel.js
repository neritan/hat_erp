// A hotel as distributors see it, read-only: the property, where it is, how to reach it, and what
// the distributor has done with it. Distributors land here instead of the Customer form.
// Route: /desk/hat-hotel/<customer>

frappe.pages["hat-hotel"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Hotel"),
		single_column: true,
	});
	wrapper.hotel_page = new HATHotelPage(page);
};

frappe.pages["hat-hotel"].on_page_show = (wrapper) => {
	wrapper.hotel_page.load(frappe.get_route()[1]);
};

class HATHotelPage {
	constructor(page) {
		this.page = page;
		this.view = new hat.profile.HotelView(
			$(`<div class="hat-profile"></div>`).appendTo(page.main)
		);
	}

	async load(name) {
		if (!name) {
			frappe.set_route("List", "Customer");
			return;
		}
		const data = await this.view.load(name);
		if (data) this.page.set_title(data.hotel.customer_name);
	}
}
