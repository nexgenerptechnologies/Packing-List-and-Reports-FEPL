frappe.ui.form.on('Sales Partner Sub Allocation', {
	refresh: function(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.sales_partner) {
			frm.add_custom_button(__('Fetch My Allocations'), function() {
				frm.events.fetch_my_allocations(frm);
			});
		}
	},
	fetch_my_allocations: function(frm) {
		frappe.call({
			method: "packing_list_reports_fepl.packing.doctype.sales_partner_sub_allocation.sales_partner_sub_allocation.get_partner_quotas",
			args: {
				sales_partner: frm.doc.sales_partner
			},
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					frm.clear_table('sub_allocations');
					r.message.forEach(row => {
						let child = frm.add_child('sub_allocations');
						child.item_code = row.item_code;
						child.item_name = row.item_name;
						child.description = row.description;
						child.quota_qty = row.allocated_qty;
					});
					frm.refresh_field('sub_allocations');
				} else {
					frappe.msgprint(__('No pending quotas found for you.'));
				}
			}
		});
	}
});

frappe.ui.form.on('Sub Allocation Detail', {
	customer: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		// Clear SO if customer changes
		frappe.model.set_value(cdt, cdn, 'sales_order', '');
	},
	sales_order: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		// Filter Sales Order by Customer
		frm.set_query('sales_order', 'sub_allocations', function() {
			return {
				filters: {
					customer: row.customer,
					docstatus: 1,
					status: ['not in', ['Closed', 'Completed', 'Cancelled']]
				}
			};
		});
	}
});
