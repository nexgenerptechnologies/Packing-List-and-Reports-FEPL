frappe.ui.form.on('Shipment Tracker', {
	refresh: function(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.supplier && frm.doc.shipment_pos && frm.doc.shipment_pos.length > 0) {
			frm.add_custom_button(__('Fetch Pending Orders'), function() {
				frm.events.fetch_pending_items(frm);
			}).addClass('btn-primary');
		}
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__('Create Purchase Receipt'), function() {
				frm.events.make_purchase_receipt(frm);
			}).addClass('btn-primary');
		}
		
		if (frm.doc.purchase_receipt) {
			frm.add_custom_button(__('Create Purchase Invoices'), function() {
				frm.events.create_purchase_invoices(frm);
			}, __('Supplier Invoices')).addClass('btn-primary');
		}
	},
	fetch_pending_items: function(frm) {
		let pos = frm.doc.shipment_pos.map(d => d.purchase_order);
		frappe.call({
			method: "packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.get_outstanding_po_items",
			args: { supplier: frm.doc.supplier, purchase_orders: pos },
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					// Force Currency Override
					if (r.message[0].currency) {
						frm.set_value('currency', r.message[0].currency);
					}
					
					frm.clear_table('shipment_items');
					r.message.forEach(row => {
						let child = frm.add_child('shipment_items');
						child.item_code = row.item_code;
						child.item_name = row.item_name;
						child.description = row.description;
						child.qty = row.qty;
						child.rate = row.rate;
						child.line_number = row.custom_line_number || row.line_number;
						child.purchase_order = row.purchase_order;
						child.purchase_order_item = row.purchase_order_item;
					});
					frm.refresh_field('shipment_items');
					frappe.show_alert({message: __('Fetched {0} Pending Items', [r.message.length]), color: 'blue'});
				}
			}
		});
	},
	make_purchase_receipt: function(frm) {
		frappe.call({
			method: "packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.make_purchase_receipt",
			args: { docname: frm.doc.name },
			callback: function(r) {
				if (r.message) {
					frappe.set_route("Form", "Purchase Receipt", r.message);
				}
			}
		});
	},
	create_purchase_invoices: function(frm) {
		if (!frm.doc.shipment_invoices || frm.doc.shipment_invoices.length === 0) {
			frappe.msgprint(__('Please enter at least one Invoice Number and Date in the table below.'));
			return;
		}
		frappe.confirm(__('This will create Draft Purchase Invoices for all lines in the table. Continue?'), () => {
			frappe.call({
				method: "packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.create_purchase_invoices",
				args: { docname: frm.doc.name },
				callback: function(r) {
					if (r.message) {
						frappe.msgprint(__('Created {0} Purchase Invoice Drafts.', [r.message.length]));
						frm.reload_doc();
					}
				}
			});
		});
	}
});

frappe.ui.form.on('Shipment Tracker', {
	onload: function(frm) {
		frm.set_query('purchase_order', 'shipment_pos', function() {
			return { filters: { supplier: frm.doc.supplier, docstatus: 1, per_received: ["<", 100] } };
		});
		frm.set_query('purchase_receipt', function() {
			return { filters: { supplier: frm.doc.supplier, docstatus: ["in", [0, 1]] } };
		});
	}
});
