frappe.ui.form.on('Item Allocation Sheet', {
	setup: function(frm) {
		frm.set_query('sales_order', 'items', function(doc, cdt, cdn) {
			let row = frappe.get_doc(cdt, cdn);
			if (row.customer) {
				return {
					filters: {
						customer: row.customer,
						docstatus: 1,
						status: ['not in', ['Completed', 'Cancelled']]
					}
				};
			}
		});
	},
	refresh: function(frm) {
		frappe.db.get_single_value('Packing List Settings', 'enable_item_allocation_sheet').then(val => {
			if (val === 0) {
				frappe.msgprint(__('Item Allocation Sheet is disabled in Settings.'));
				frm.disable_save();
			}
		});

		frm.clear_custom_buttons();
		if (frm.doc.status === 'Draft') {
			frm.add_custom_button(__('Send to Team Leader'), function() {
				frm.set_value('status', 'Pending Team Leader');
				frm.save();
			}).addClass('btn-primary');
		}

		if (frm.doc.status === 'Pending Team Leader') {
			frm.add_custom_button(__('Approve Allocation'), function() {
				frm.set_value('status', 'Approved');
				frm.save();
			}).addClass('btn-primary');
			frm.add_custom_button(__('Reject'), function() {
				frm.set_value('status', 'Draft');
				frm.save();
			}).addClass('btn-danger');
		}

		if (frm.doc.status !== 'Draft') {
			frm.set_df_property('shipments', 'read_only', 1);
		}
		
		let is_tl = frappe.user.has_role('System Manager') || frappe.user.has_role('Sales Manager');
		
		let items_grid = frm.fields_dict['items'].grid;
		if (frm.doc.status === 'Approved') {
			items_grid.update_docfield_property('customer', 'read_only', 1);
			items_grid.update_docfield_property('sales_order', 'read_only', 1);
			items_grid.update_docfield_property('partner_allocation_qty', 'read_only', 1);
			items_grid.update_docfield_property('allocated_qty', 'read_only', 1);
		} else if (frm.doc.status === 'Pending Team Leader') {
			items_grid.update_docfield_property('customer', 'read_only', 1);
			items_grid.update_docfield_property('sales_order', 'read_only', 1);
			items_grid.update_docfield_property('partner_allocation_qty', 'read_only', 1);
			if (is_tl) {
				items_grid.update_docfield_property('allocated_qty', 'read_only', 0);
			} else {
				items_grid.update_docfield_property('allocated_qty', 'read_only', 1);
			}
		} else {
			items_grid.update_docfield_property('customer', 'read_only', 0);
			items_grid.update_docfield_property('sales_order', 'read_only', 0);
			items_grid.update_docfield_property('partner_allocation_qty', 'read_only', 0);
			items_grid.update_docfield_property('allocated_qty', 'read_only', 1);
		}
	}
});

frappe.ui.form.on('Item Allocation Shipment', {
	shipment_tracker: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		if (row.shipment_tracker) {
			frappe.call({
				method: 'frappe.client.get',
				args: {
					doctype: 'Shipment Tracker',
					name: row.shipment_tracker
				},
				callback: function(r) {
					if (r.message && r.message.shipment_items) {
						r.message.shipment_items.forEach(function(item) {
							let new_row = frm.add_child('items');
							new_row.shipment = row.shipment_tracker;
							new_row.item_code = item.item_code;
							new_row.item_name = item.item_name;
							new_row.description = item.description;
							new_row.total_qty = item.qty;
						});
						frm.refresh_field('items');
					}
				}
			});
		}
	}
});
