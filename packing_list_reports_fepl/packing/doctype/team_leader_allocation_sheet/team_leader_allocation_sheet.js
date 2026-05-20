// -*- coding: utf-8 -*-
// Copyright (c) 2026, Administrator and contributors
// For license information, please see license.txt

frappe.ui.form.on('Team Leader Allocation Sheet', {
	setup: function(frm) {
		// Filter Shipment link inside shipments table to only show submitted Shipment Trackers
		frm.set_query('shipment_tracker', 'shipments', function() {
			return {
				filters: {
					docstatus: 1
				}
			};
		});
	},
	refresh: function(frm) {
		frm.clear_custom_buttons();
		
		if (frm.doc.status === 'Draft') {
			// 1. Fetch Partner Requests
			frm.add_custom_button(__('Fetch Partner Requests'), function() {
				frm.save().then(() => {
					frappe.call({
						method: 'packing_list_reports_fepl.packing.doctype.team_leader_allocation_sheet.team_leader_allocation_sheet.fetch_partner_requests',
						args: { docname: frm.doc.name },
						callback: function(r) {
							if (!r.exc) {
								frappe.show_alert({message: __(r.message), color: 'green'});
								frm.reload_doc();
							}
						}
					});
				});
			}).addClass('btn-primary');
			
			// 2. Download Template
			frm.add_custom_button(__('Download Template'), function() {
				let url = '/api/method/packing_list_reports_fepl.packing.doctype.team_leader_allocation_sheet.team_leader_allocation_sheet.download_tl_template';
				if (!frm.is_new()) {
					url += '?docname=' + frm.doc.name;
				}
				window.open(url);
			});
			
			// 3. Upload Excel
			if (frm.doc.excel_file) {
				frm.add_custom_button(__('Upload Excel Data'), function() {
					frm.save().then(() => {
						frappe.call({
							method: 'packing_list_reports_fepl.packing.doctype.team_leader_allocation_sheet.team_leader_allocation_sheet.upload_tl_excel',
							args: { docname: frm.doc.name },
							callback: function(r) {
								if (!r.exc) {
									frappe.show_alert({message: __(r.message), color: 'green'});
									frm.reload_doc();
								}
							}
						});
					});
				}).addClass('btn-primary');
			}
			
			// 4. Approve & Distribute
			if (frm.doc.items && frm.doc.items.length > 0) {
				frm.add_custom_button(__('Approve & Distribute Quotas'), function() {
					frappe.confirm(__('Are you sure you want to approve and distribute these quotas to all Sales Partners? This will update their individual sheets and transition them to Partner Finalization stage.'), function() {
						frm.save().then(() => {
							frappe.call({
								method: 'packing_list_reports_fepl.packing.doctype.team_leader_allocation_sheet.team_leader_allocation_sheet.distribute_tl_quotas',
								args: { docname: frm.doc.name },
								callback: function(r) {
									if (!r.exc) {
										frappe.msgprint(__('Quotas successfully approved and distributed to all Sales Partners.'));
										frm.reload_doc();
									}
								}
							});
						});
					});
				}).addClass('btn-success');
			}
		}
		
		// Set read only rules
		let items_grid = frm.fields_dict['items'].grid;
		if (frm.doc.status === 'Approved') {
			frm.set_df_property('shipments', 'read_only', 1);
			frm.set_df_property('excel_file', 'read_only', 1);
			items_grid.update_docfield_property('allocated_qty', 'read_only', 1);
		} else {
			frm.set_df_property('shipments', 'read_only', 0);
			frm.set_df_property('excel_file', 'read_only', 0);
			items_grid.update_docfield_property('allocated_qty', 'read_only', 0);
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
					if (r.message) {
						// Auto-populate Supplier Name, ETD, ETA on child row
						frappe.model.set_value(cdt, cdn, 'supplier', r.message.supplier);
						frappe.model.set_value(cdt, cdn, 'etd', r.message.etd);
						frappe.model.set_value(cdt, cdn, 'eta', r.message.eta);
					}
				}
			});
		}
	}
});
