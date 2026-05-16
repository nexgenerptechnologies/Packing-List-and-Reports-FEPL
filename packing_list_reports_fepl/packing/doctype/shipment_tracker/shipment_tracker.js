frappe.ui.form.on('Shipment Tracker', {
	setup: function(frm) {
		frm.set_query('purchase_order', function() {
			return {
				filters: {
					supplier: frm.doc.supplier,
					docstatus: 1,
					status: ["not in", ["Closed", "Completed", "Cancelled"]]
				}
			};
		});
	},
	refresh: function(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.purchase_order) {
			frm.add_custom_button(__('Fetch Pending Orders'), function() {
				frm.events.fetch_pending_items(frm);
			});
		}
	},
	fetch_pending_items: function(frm) {
		frappe.call({
			method: "packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.get_outstanding_po_items",
			args: {
				supplier: frm.doc.supplier,
				purchase_order: frm.doc.purchase_order
			},
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					frm.clear_table('shipment_items');
					r.message.forEach(row => {
						let child = frm.add_child('shipment_items');
						child.item_code = row.item_code;
						child.item_name = row.item_name;
						child.description = row.description;
						child.qty = row.qty;
						child.rate = row.rate;
						// Use either custom_line_number or line_number
						child.line_number = row.custom_line_number || row.line_number;
					});
					frm.refresh_field('shipment_items');
					frappe.show_alert({message: __('Fetched {0} Pending Items', [r.message.length]), color: 'blue'});
				} else {
					frappe.msgprint(__('No pending items found for this Purchase Order.'));
				}
			}
		});
	}
});
