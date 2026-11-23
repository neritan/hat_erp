// A distributor as hotels see it, read-only: who they are, where they deliver, how hotels rate them,
// and what they sell. Hotels land here instead of the Supplier form.
// Route: /desk/hat-distributor/<supplier>

frappe.pages["hat-distributor"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Distributor"),
		single_column: true,
	});
	wrapper.distributor_page = new HATDistributorPage(page);
};

frappe.pages["hat-distributor"].on_page_show = (wrapper) => {
	wrapper.distributor_page.load(frappe.get_route()[1]);
};

class HATDistributorPage {
	constructor(page) {
		this.page = page;
		this.view = new hat.profile.DistributorView(
			$(`<div class="hat-profile"></div>`).appendTo(page.main)
		);
		this.page.set_secondary_action(
			__("Marketplace"),
			() => frappe.set_route("hat-marketplace"),
			"store"
		);
	}

	async load(name) {
		if (!name) {
			frappe.set_route("hat-marketplace");
			return;
		}
		const data = await this.view.load(name);
		if (data) this.page.set_title(data.distributor.supplier_name);
	}
}
