// Copyright (c) 2026, HAT and contributors
// For license information, please see license.txt

frappe.ui.form.on("HAT Quote", {
	setup(frm) {
		frm.set_query("distributor", () => ({ filters: { supplier_group: "Distributor" } }));
		frm.set_query("quote_request", () => ({ filters: { status: "Open" } }));
	},

	quote_request: (frm) => fill_lines(frm),
	distributor: (frm) => fill_lines(frm),

	refresh(frm) {
		if (frm.is_new()) return;
		const can_write = frm.perm[0]?.write;
		const status = frm.doc.status;

		if (can_write && status === "Draft") {
			frm.add_custom_button(__("Submit Quote"), () =>
				frm
					.save()
					.then(() => frm.call("submit_quote"))
					.then(() => frm.reload_doc())
			);
			frm.change_custom_button_type(__("Submit Quote"), null, "primary");
		}
		if (can_write && ["Draft", "Submitted"].includes(status)) {
			frm.add_custom_button(
				__("Withdraw"),
				() =>
					frappe.confirm(__("Withdraw this quote?"), () =>
						frm.call("withdraw").then(() => frm.reload_doc())
					),
				__("Actions")
			);
		}

		const deadline = frappe.datetime.str_to_user(frm.doc.quote_deadline);
		const intro = {
			Draft: [
				__("Draft: the hotel sees your quote once you submit it. Due by {0}.", [deadline]),
				"yellow",
			],
			Submitted: [
				__("Submitted. You can still change prices until {0}.", [deadline]),
				"blue",
			],
			Awarded: [__("Awarded: an order was sent to you for the products you won."), "green"],
			"Not Awarded": [__("The hotel chose other quotes this time."), "gray"],
		}[status];
		if (intro) frm.set_intro(intro[0], intro[1]);
		frm.set_df_property("items", "read_only", ["Draft", "Submitted"].includes(status) ? 0 : 1);
	},
});

// The request's products, priced from the distributor's listings (the server re-syncs on save)
function fill_lines(frm) {
	if (!frm.is_new() || !frm.doc.quote_request) return;
	frappe
		.call("hat.hospitality_and_tourism_academy.doctype.hat_quote.hat_quote.get_quote_lines", {
			quote_request: frm.doc.quote_request,
			distributor: frm.doc.distributor,
		})
		.then(({ message }) => {
			frm.clear_table("items");
			message.forEach((line) => frm.add_child("items", line));
			frm.refresh_field("items");
			frm.doc.items.forEach((row) => update_amount(frm, row.doctype, row.name));
		});
}

frappe.ui.form.on("HAT Quote Item", {
	rate: (frm, cdt, cdn) => update_amount(frm, cdt, cdn),
	can_supply: (frm, cdt, cdn) => update_amount(frm, cdt, cdn),
});

function update_amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(
		cdt,
		cdn,
		"amount",
		row.can_supply ? (row.qty || 0) * (row.rate || 0) : 0
	);
	frm.set_value(
		"total_amount",
		frm.doc.items.reduce(
			(sum, r) => sum + (r.can_supply ? (r.qty || 0) * (r.rate || 0) : 0),
			0
		)
	);
}
