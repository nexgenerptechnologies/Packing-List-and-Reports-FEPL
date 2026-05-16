frappe.ui.form.on('Shipment Tracker', {
	refresh: function(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.shipment_pos && frm.doc.shipment_pos.length > 0) {
			frm.add_custom_button(__('Fetch Pending Orders'), function() {
				frm.events.fetch_pending_items(frm);
			});
		}
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__('Create Purchase Receipt'), function() {
				frm.events.make_purchase_receipt(frm);
			});
		}
	},
	fetch_pending_items: function(frm) {
		let pos = frm.doc.shipment_pos.map(d => d.purchase_order);
		
		frappe.call({
			method: "packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.get_outstanding_po_items",
			args: {
				supplier: frm.doc.supplier,
				purchase_orders: pos
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
						child.line_number = row.custom_line_number || row.line_number;
						// Store hidden links for PR creation
						child.purchase_order = row.purchase_order;
						child.purchase_order_item = row.purchase_order_item;
					});
					frm.refresh_field('shipment_items');
					frappe.show_alert({message: __('Fetched {0} Pending Items from {1} POs', [r.message.length, pos.length]), color: 'blue'});
				} else {
					frappe.msgprint(__('No pending items found for the selected Purchase Orders.'));
				}
			}
		});
	},
	make_purchase_receipt: function(frm) {
		frappe.call({
			method: "packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.make_purchase_receipt",
			args: {
				docname: frm.doc.name
			},
			callback: function(r) {
				if (r.message) {
					frappe.set_route("Form", "Purchase Receipt", r.message);
				}
			}
		});
	}
});

frappe.ui.form.on('Shipment Tracker', {
	onload: function(frm) {
		frm.set_query('purchase_order', 'shipment_pos', function() {
			return {
				filters: {
					supplier: frm.doc.supplier,
					docstatus: 1,
					status: ["not in", ["Closed", "Completed", "Cancelled"]],
					per_received: ["<", 100]
				}
			};
		});
	},
	supplier: function(frm) {
		frm.clear_table('shipment_pos');
		frm.refresh_field('shipment_pos');
	}
});
