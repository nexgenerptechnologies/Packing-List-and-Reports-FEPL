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
			if (val === 0 || val === "0") {
				frappe.msgprint({
					title: __('Allocation Disabled'),
					indicator: 'red',
					message: __('Item Allocation Sheet is disabled. Click <a href="/app/packing-list-settings">here</a> to go to Settings and enable it.')
				});
				frm.disable_save();
			}
		});

		frm.clear_custom_buttons();
		
		// 1. Download Template Buttons
		if (frm.doc.status === 'Draft') {
			frm.add_custom_button(__('Download Partner Template'), function() {
				window.open('/api/method/packing_list_reports_fepl.packing.doctype.item_allocation_sheet.item_allocation_sheet.download_partner_template');
			});
		} else if (frm.doc.status === 'Pending Team Leader') {
			frm.add_custom_button(__('Download Team Lead Template'), function() {
				window.open('/api/method/packing_list_reports_fepl.packing.doctype.item_allocation_sheet.item_allocation_sheet.download_team_leader_template?docname=' + frm.doc.name);
			});
		}

		// 2. Upload Excel Action
		if (frm.doc.excel_file && (frm.doc.status === 'Draft' || frm.doc.status === 'Pending Team Leader')) {
			frm.add_custom_button(__('Upload Excel Data'), function() {
				frappe.call({
					method: 'packing_list_reports_fepl.packing.doctype.item_allocation_sheet.item_allocation_sheet.upload_excel_data',
					args: { docname: frm.doc.name },
					callback: function(r) {
						if (!r.exc) {
							frappe.show_alert({message: __('Excel data loaded successfully.'), color: 'green'});
							frm.reload_doc();
						}
					}
				});
			}).addClass('btn-primary');
		}

		// 3. Workflow Action Buttons
		if (frm.doc.status === 'Draft') {
			frm.add_custom_button(__('Send to Team Leader'), function() {
				frm.set_value('status', 'Pending Team Leader');
				frm.save().then(() => {
					frappe.msgprint(__('Sent to Team Leader successfully.'));
					frm.reload_doc();
				});
			}).addClass('btn-primary');
		}

		if (frm.doc.status === 'Pending Team Leader') {
			frm.add_custom_button(__('Approve Allocation'), function() {
				frm.set_value('status', 'Approved');
				frm.save().then(() => {
					frappe.msgprint(__('Allocation approved successfully.'));
					frm.reload_doc();
				});
			}).addClass('btn-primary');
			frm.add_custom_button(__('Reject'), function() {
				frm.set_value('status', 'Draft');
				frm.save().then(() => {
					frappe.msgprint(__('Allocation rejected and sent back to Draft.'));
					frm.reload_doc();
				});
			}).addClass('btn-danger');
		}

		// 4. Role and Status Read Only Enforcements
		if (frm.doc.status !== 'Draft') {
			frm.set_df_property('shipments', 'read_only', 1);
		} else {
			frm.set_df_property('shipments', 'read_only', 0);
		}
		
		let is_tl = frappe.user.has_role('System Manager') || frappe.user.has_role('Sales Manager');
		let items_grid = frm.fields_dict['items'].grid;
		
		if (frm.doc.status === 'Approved') {
			items_grid.update_docfield_property('customer', 'read_only', 1);
			items_grid.update_docfield_property('sales_order', 'read_only', 1);
			items_grid.update_docfield_property('allocation_request', 'read_only', 1);
			items_grid.update_docfield_property('allocated_qty', 'read_only', 1);
			frm.set_df_property('excel_file', 'read_only', 1);
		} else if (frm.doc.status === 'Pending Team Leader') {
			items_grid.update_docfield_property('customer', 'read_only', 1);
			items_grid.update_docfield_property('sales_order', 'read_only', 1);
			items_grid.update_docfield_property('allocation_request', 'read_only', 1);
			if (is_tl) {
				items_grid.update_docfield_property('allocated_qty', 'read_only', 0);
				frm.set_df_property('excel_file', 'read_only', 0);
			} else {
				items_grid.update_docfield_property('allocated_qty', 'read_only', 1);
				frm.set_df_property('excel_file', 'read_only', 1);
			}
		} else { // Draft
			items_grid.update_docfield_property('customer', 'read_only', 0);
			items_grid.update_docfield_property('sales_order', 'read_only', 0);
			items_grid.update_docfield_property('allocation_request', 'read_only', 0);
			items_grid.update_docfield_property('allocated_qty', 'read_only', 1);
			frm.set_df_property('excel_file', 'read_only', 0);
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

frappe.ui.form.on('Partner Allocation Detail', {
	allocation_request: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		if (row.item_code) {
			let total = 0;
			frm.doc.items.forEach(function(item) {
				if (item.item_code === row.item_code) {
					total += flt(item.allocation_request);
				}
			});
			frm.doc.items.forEach(function(item) {
				if (item.item_code === row.item_code) {
					frappe.model.set_value(item.doctype, item.name, 'total_allocation_request', total);
				}
			});
		}
	}
});
