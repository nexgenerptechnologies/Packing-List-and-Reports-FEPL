frappe.ui.form.on('Shipment Tracker', {
	refresh: function(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.supplier) {
			frm.add_custom_button(__('Fetch Outstanding POs'), function() {
				frm.events.fetch_outstanding_pos(frm);
			});
		}
	},
	fetch_outstanding_pos: function(frm) {
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Purchase Order",
				filters: {
					supplier: frm.doc.supplier,
					docstatus: 1,
					status: ["not in", ["Closed", "Completed", "Cancelled"]]
				},
				fields: ["name", "transaction_date", "grand_total"]
			},
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					let d = new frappe.ui.Dialog({
						title: __('Select Purchase Orders'),
						fields: [
							{
								label: __('Purchase Orders'),
								fieldname: 'pos',
								fieldtype: 'MultiCheck',
								options: r.message.map(po => ({
									label: `${po.name} (${po.transaction_date})`,
									value: po.name,
									checked: false
								}))
							}
						],
						primary_action_label: __('Fetch Items'),
						primary_action(values) {
							if (values.pos && values.pos.length > 0) {
								frm.events.load_po_items(frm, values.pos);
							}
							d.hide();
						}
					});
					d.show();
				} else {
					frappe.msgprint(__('No outstanding Purchase Orders found for this supplier.'));
				}
			}
		});
	},
	load_po_items: function(frm, pos) {
		frappe.call({
			method: "packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.get_outstanding_po_items",
			args: {
				supplier: frm.doc.supplier,
				purchase_orders: pos
			},
			callback: function(r) {
				if (r.message) {
					frm.clear_table('shipment_items');
					r.message.forEach(row => {
						let child = frm.add_child('shipment_items');
						child.item_code = row.item_code;
						child.item_name = row.item_name;
						child.description = row.description;
						child.qty = row.qty;
						child.rate = row.rate;
						child.custom_line_number = row.custom_line_number;
						child.purchase_order = row.purchase_order;
						child.purchase_order_item = row.purchase_order_item;
					});
					frm.refresh_field('shipment_items');
				}
			}
		});
	}
});
