// Copyright (c) 2026, HAT and contributors
// For license information, please see license.txt

const QUOTE_REQUEST_API =
	"hat.hospitality_and_tourism_academy.doctype.hat_quote_request.hat_quote_request";
const is_hat_staff = () =>
	frappe.user.has_role("HAT Staff") || frappe.user.has_role("System Manager");

frappe.ui.form.on("HAT Quote Request", {
	setup(frm) {
		frm.set_query("hotel", () => ({ filters: { customer_group: "Hotel" } }));
		frm.set_query("item_group", "items", () => ({ filters: { is_group: 0 } }));
		frm.set_query("item", "items", () => ({ filters: { disabled: 0, has_variants: 0 } }));
	},

	refresh(frm) {
		if (frm.is_new()) return;
		const can_write = frm.perm[0]?.write;
		const status = frm.doc.status;

		if (can_write && status === "Draft") {
			frm.add_custom_button(__("Publish"), () =>
				frm.call("publish").then(() => frm.reload_doc())
			);
			frm.change_custom_button_type(__("Publish"), null, "primary");
		}
		if (can_write && ["Open", "Closed"].includes(status)) {
			frm.add_custom_button(__("Compare & Award"), () => compare_and_award(frm));
			frm.change_custom_button_type(__("Compare & Award"), null, "primary");
		}
		if (can_write && status === "Open") {
			frm.add_custom_button(
				__("Close"),
				() => frm.call("close").then(() => frm.reload_doc()),
				__("Actions")
			);
		}
		if (can_write && ["Draft", "Open", "Closed"].includes(status)) {
			frm.add_custom_button(
				__("Cancel Request"),
				() =>
					frappe.confirm(__("Cancel this quote request?"), () =>
						frm.call("cancel_request").then(() => frm.reload_doc())
					),
				__("Actions")
			);
		}
		if (frappe.user.has_role("Distributor") && !is_hat_staff() && status === "Open") {
			frm.add_custom_button(__("Send Quote"), () =>
				frappe
					.call(`${QUOTE_REQUEST_API}.make_quote`, { quote_request: frm.doc.name })
					.then(({ message }) => frappe.set_route("Form", "HAT Quote", message))
			);
			frm.change_custom_button_type(__("Send Quote"), null, "primary");
		}

		const deadline = frappe.datetime.str_to_user(frm.doc.quote_deadline);
		const intro = {
			Draft: [__("Draft: distributors see it once you publish."), "yellow"],
			Open: [
				__("Open for quotes until {0}. Quotes received: {1}.", [
					deadline,
					frm.doc.quote_count || 0,
				]),
				"blue",
			],
			Closed: [
				__("Closed for new quotes. Compare and award the quotes received ({0}).", [
					frm.doc.quote_count || 0,
				]),
				"orange",
			],
			Awarded: [__("Awarded. Orders were sent to the selected distributors."), "green"],
		}[status];
		if (intro) frm.set_intro(intro[0], intro[1]);
	},
});

// Products × submitted quotes; the hotel picks one quote per product (cheapest pre-selected)
async function compare_and_award(frm) {
	const { message: data } = await frm.call("get_comparison");
	if (!data.quotes.length) {
		frappe.msgprint(__("No quotes have been submitted yet."));
		return;
	}
	const esc = frappe.utils.escape_html;
	const money = (v) => format_currency(v, "ALL", 0);
	const header = data.quotes
		.map(
			(q) => `<th class="text-right">
				<a href="/desk/hat-quote/${encodeURIComponent(q.name)}" target="_blank">${esc(
				q.distributor_name
			)}</a>
				<div class="text-muted small">
					${q.rating ? `★ ${(q.rating * 5).toFixed(1)} · ` : ""}${
				q.delivery_days ? __("{0} days", [q.delivery_days]) : ""
			}
				</div></th>`
		)
		.join("");
	const rows = data.lines
		.map((line) => {
			const offered = data.quotes.filter((q) => q.rates[line.name]);
			const best = offered.length
				? offered.reduce((a, b) => (a.rates[line.name] <= b.rates[line.name] ? a : b)).name
				: null;
			const cells = data.quotes
				.map((q) => {
					const rate = q.rates[line.name];
					if (!rate) return `<td class="text-right text-muted">—</td>`;
					const checked = q.name === best ? "checked" : "";
					return `<td class="text-right">
						<label class="hat-award-cell ${q.name === best ? "hat-award-best" : ""}">
							<input type="radio" name="${esc(line.name)}" value="${esc(q.name)}" ${checked}>
							${money(rate)}
							<div class="text-muted small">${money(rate * line.qty)}</div>
						</label></td>`;
				})
				.join("");
			return `<tr>
				<td>${esc(line.description)}<div class="text-muted small">${line.qty} ${esc(
				__(line.uom || "")
			)}</div></td>
				${cells}
				<td class="text-center"><input type="radio" name="${esc(line.name)}" value="" ${
				best ? "" : "checked"
			}></td>
			</tr>`;
		})
		.join("");

	const dialog = new frappe.ui.Dialog({
		title: __("Compare quotes: {0}", [frm.doc.title]),
		size: "extra-large",
		fields: [{ fieldname: "grid", fieldtype: "HTML" }],
		primary_action_label: __("Award & Send Orders"),
		primary_action: async () => {
			const awards = {};
			dialog.$wrapper.find("input[type=radio]:checked").each((_, input) => {
				if (input.value) awards[input.name] = input.value;
			});
			if (!Object.keys(awards).length) {
				frappe.msgprint(__("Choose a quote for at least one product."));
				return;
			}
			const { message: orders } = await frm.call({
				method: "award",
				args: { awards },
				freeze: true,
				freeze_message: __("Sending orders..."),
			});
			dialog.hide();
			frappe.msgprint({
				title: __("Orders sent"),
				indicator: "green",
				message: orders
					.map((o) => `<a href="/desk/hat-order-request/${o}">${o}</a>`)
					.join("<br>"),
			});
			frm.reload_doc();
		},
	});
	dialog.fields_dict.grid.$wrapper.html(`
		<p class="text-muted small">${__(
			"The cheapest price per product is selected. Pick another distributor or 'None' to leave a product out. One order is sent to each selected distributor."
		)}</p>
		<div class="table-responsive">
			<table class="table table-bordered hat-award-table">
				<thead><tr><th>${__("Product")}</th>${header}<th class="text-center">${__(
		"None"
	)}</th></tr></thead>
				<tbody>${rows}</tbody>
				<tfoot><tr><th>${__("Quote total")}</th>${data.quotes
		.map((q) => `<th class="text-right">${money(q.total_amount)}</th>`)
		.join("")}<th></th></tr></tfoot>
			</table>
		</div>`);
	dialog.show();
}

frappe.dom.set_style(`
	.hat-award-table td, .hat-award-table th { vertical-align: middle; }
	.hat-award-cell { display: block; margin: 0; cursor: pointer; font-weight: normal; }
	.hat-award-cell input { margin-right: 4px; }
	.hat-award-best { color: var(--green-600, #16a34a); font-weight: 600; }
`);
