frappe.ui.form.on('Item Allocation Sheet', {
	onload: function(frm) {
		if (!frm.doc.sales_partner) {
			frappe.call({
				method: "packing_list_reports_fepl.packing.doctype.item_allocation_sheet.item_allocation_sheet.get_sales_partner_for_user",
				args: { user: frappe.session.user },
				callback: function(r) {
					if (r.message) {
						frm.set_value("sales_partner", r.message);
					} else {
						let is_manager = frappe.user_roles.includes("System Manager") || frappe.user_roles.includes("Sales Manager") || frappe.session.user === "Administrator";
						if (!is_manager) {
							frappe.msgprint({
								title: __('Access Restriction'),
								indicator: 'red',
								message: __('Your user login "{0}" is not registered as a Sales Partner in the system. You will not be allowed to save or submit this sheet.', [frappe.session.user])
							});
							frappe.validated = false;
						}
					}
				}
			});
		}
	},
	before_save: function(frm) {
		if (frm.doc.sales_partner) {
			frm.doc.items.forEach(row => {
				row.sales_partner = frm.doc.sales_partner;
			});
			frm.refresh_field('items');
		} else {
			frappe.msgprint({
				title: __('Validation Error'),
				indicator: 'red',
				message: __('Please select a Sales Partner before saving.')
			});
			frappe.validated = false;
		}
	},
	setup: function(frm) {
		// Filter Sales Orders to only show pending orders for the selected customer
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

		// Filter Item Code to only show items that exist in the selected shipments
		frm.set_query('item_code', 'items', function(doc) {
			let allowed_items = [];
			if (doc.items) {
				doc.items.forEach(d => {
					if (d.item_code && !allowed_items.includes(d.item_code)) {
						allowed_items.push(d.item_code);
					}
				});
			}
			return {
				filters: {
					name: ['in', allowed_items]
				}
			};
		});

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
		let is_manager = frappe.user.has_role('System Manager') || frappe.user.has_role('Sales Manager') || frappe.session.user === 'Administrator';
		if (is_manager) {
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
		}

		frm.clear_custom_buttons();
		
		// Hide native submit button unless we are in the correct finalization state
		if (frm.doc.docstatus === 0 && frm.doc.status !== 'Pending Partner Finalization') {
			frm.page.clear_primary_action();
		}
		
		// 1. Download Template Buttons
		if (frm.doc.status === 'Draft') {
			frm.add_custom_button(__('Download Partner Template'), function() {
				const perform_download = () => {
					let url = '/api/method/packing_list_reports_fepl.packing.doctype.item_allocation_sheet.item_allocation_sheet.download_partner_template';
					url += '?docname=' + frm.doc.name;
					window.open(url);
				};
				
				if (frm.is_new() || frm.is_dirty()) {
					frappe.confirm(__('The document must be saved first to register the fetched items in the template. Save and download?'), function() {
						frm.save().then(perform_download);
					});
				} else {
					perform_download();
				}
			});
		} else if (frm.doc.status === 'Pending Team Leader') {
			frm.add_custom_button(__('Download Team Lead Template'), function() {
				window.open('/api/method/packing_list_reports_fepl.packing.doctype.item_allocation_sheet.item_allocation_sheet.download_team_leader_template?docname=' + frm.doc.name);
			});
		} else if (frm.doc.status === 'Pending Partner Finalization') {
			frm.add_custom_button(__('Download Finalization Template'), function() {
				window.open('/api/method/packing_list_reports_fepl.packing.doctype.item_allocation_sheet.item_allocation_sheet.download_partner_finalization_template?docname=' + frm.doc.name);
			});
		}

		// 2. Upload Excel Action
		if (frm.doc.excel_file && frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Upload Excel Data'), function() {
				const perform_call = () => {
					frappe.call({
						method: 'packing_list_reports_fepl.packing.doctype.item_allocation_sheet.item_allocation_sheet.upload_excel_data',
						args: { docname: frm.doc.name },
						freeze: true,
						callback: function(r) {
							if (!r.exc) {
								frappe.show_alert({message: __('Excel data loaded successfully.'), color: 'green'});
								frm.reload_doc();
							}
						}
					});
				};
				if (frm.is_dirty()) {
					frm.save().then(perform_call);
				} else {
					perform_call();
				}
			}).addClass('btn-primary');
		}

		// 3. Workflow Action Buttons
		if (frm.doc.status === 'Draft' && frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Send to Team Leader'), function() {
				frm.set_value('status', 'Pending Team Leader');
				frm.save().then(() => {
					frappe.msgprint(__('Sent to Team Leader successfully.'));
					frm.reload_doc();
				});
			}).addClass('btn-primary');
		}

		let is_tl = frappe.user.has_role('System Manager') || frappe.user.has_role('Sales Manager');


		// 4. Role and Status Read Only Enforcements
		if (frm.doc.status !== 'Draft') {
			frm.set_df_property('shipments', 'read_only', 1);
		} else {
			frm.set_df_property('shipments', 'read_only', 0);
		}

		let is_manager = frappe.user.has_role('System Manager') || frappe.user.has_role('Sales Manager') || frappe.session.user === 'Administrator';
		if (frm.doc.status === 'Draft' && (is_manager || !frm.doc.sales_partner)) {
			frm.set_df_property('sales_partner', 'read_only', 0);
		} else {
			frm.set_df_property('sales_partner', 'read_only', 1);
		}
		
		let items_grid = frm.fields_dict['items'].grid;
		
		if (frm.doc.docstatus === 1) { // Submitted/Approved
			items_grid.update_docfield_property('item_code', 'read_only', 1);
			items_grid.update_docfield_property('customer', 'read_only', 1);
			items_grid.update_docfield_property('sales_order', 'read_only', 1);
			items_grid.update_docfield_property('allocation_request', 'read_only', 1);
			items_grid.update_docfield_property('allocated_qty', 'read_only', 1);
			items_grid.update_docfield_property('final_allocation', 'read_only', 1);
			frm.set_df_property('excel_file', 'read_only', 1);
		} else if (frm.doc.status === 'Pending Team Leader') {
			items_grid.update_docfield_property('item_code', 'read_only', 1);
			items_grid.update_docfield_property('customer', 'read_only', 1);
			items_grid.update_docfield_property('sales_order', 'read_only', 1);
			items_grid.update_docfield_property('allocation_request', 'read_only', 1);
			items_grid.update_docfield_property('final_allocation', 'read_only', 1);
			if (is_tl) {
				items_grid.update_docfield_property('allocated_qty', 'read_only', 0);
				frm.set_df_property('excel_file', 'read_only', 0);
			} else {
				items_grid.update_docfield_property('allocated_qty', 'read_only', 1);
				frm.set_df_property('excel_file', 'read_only', 1);
			}
		} else if (frm.doc.status === 'Pending Partner Finalization') {
			items_grid.update_docfield_property('item_code', 'read_only', 1);
			items_grid.update_docfield_property('customer', 'read_only', 1);
			items_grid.update_docfield_property('sales_order', 'read_only', 1);
			items_grid.update_docfield_property('allocation_request', 'read_only', 1);
			items_grid.update_docfield_property('allocated_qty', 'read_only', 1);
			
			if (!is_tl) {
				items_grid.update_docfield_property('final_allocation', 'read_only', 0);
				frm.set_df_property('excel_file', 'read_only', 0);
			} else {
				items_grid.update_docfield_property('final_allocation', 'read_only', 1);
				frm.set_df_property('excel_file', 'read_only', 1);
			}
			
			frm.page.set_primary_action(__('Submit Allocation'), function() {
				frm.savesubmit();
			});
		} else { // Draft
			items_grid.update_docfield_property('item_code', 'read_only', 0);
			items_grid.update_docfield_property('customer', 'read_only', 0);
			items_grid.update_docfield_property('sales_order', 'read_only', 0);
			items_grid.update_docfield_property('allocation_request', 'read_only', 0);
			items_grid.update_docfield_property('allocated_qty', 'read_only', 1);
			items_grid.update_docfield_property('final_allocation', 'read_only', 1);
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
					if (r.message) {
						// Auto-populate Supplier Name, ETD, ETA on child row
						frappe.model.set_value(cdt, cdn, 'supplier', r.message.supplier);
						frappe.model.set_value(cdt, cdn, 'etd', r.message.etd);
						frappe.model.set_value(cdt, cdn, 'eta', r.message.eta);

						if (r.message.shipment_items) {
							// Group and club shipment items by item_code
							let clubbed_items = {};
							r.message.shipment_items.forEach(function(item) {
								let key = item.item_code.trim();
								if (!clubbed_items[key]) {
									clubbed_items[key] = {
										shipment: row.shipment_tracker,
										item_code: item.item_code,
										item_name: item.item_name,
										description: item.description,
										total_qty: 0.0
									};
								}
								clubbed_items[key].total_qty += flt(item.qty);
							});

							// Filter out completely blank/empty rows before appending items
							if (frm.doc.items) {
								frm.doc.items = frm.doc.items.filter(d => d.item_code || d.customer || d.allocation_request);
							}
							
							// Append the clubbed items
							Object.values(clubbed_items).forEach(function(c_item) {
								let existing = frm.doc.items ? frm.doc.items.find(d => d.item_code === c_item.item_code) : null;
								if (existing) {
									existing.total_qty = flt(existing.total_qty) + flt(c_item.total_qty);
								} else {
									let new_row = frm.add_child('items');
									new_row.shipment = c_item.shipment;
									new_row.item_code = c_item.item_code;
									new_row.item_name = c_item.item_name;
									new_row.description = c_item.description;
									new_row.total_qty = c_item.total_qty;
								}
							});
							frm.refresh_field('items');
						}
					}
				}
			});
		}
	}
});

frappe.ui.form.on('Partner Allocation Detail', {
	split_row: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		if (frm.doc.status !== 'Draft' && frm.doc.status !== 'Pending Partner Finalization') {
			frappe.msgprint(__('You can only split allocation rows in Draft or Partner Finalization stages.'));
			return;
		}
		
		frappe.prompt([
			{
				label: __('Number of splits'),
				fieldname: 'splits',
				fieldtype: 'Int',
				default: 1,
				reqd: 1
			}
		], function(values){
			let num = values.splits;
			if (num > 0) {
				let items = frm.doc.items || [];
				let clicked_index = items.indexOf(row);
				
				if (clicked_index !== -1) {
					let new_rows = [];
					for (let i = 0; i < num; i++) {
						let new_row = frappe.model.add_child(frm.doc, 'Partner Allocation Detail', 'items');
						new_row.shipment = row.shipment;
						new_row.item_code = row.item_code;
						new_row.item_name = row.item_name;
						new_row.description = row.description;
						new_row.total_qty = row.total_qty;
						new_row.sales_partner = row.sales_partner;
						new_row.allocated_qty = row.allocated_qty;
						
						new_row.customer = '';
						new_row.sales_order = '';
						new_row.allocation_request = 0;
						new_row.final_allocation = 0;
						new_rows.push(new_row);
					}
					
					// Remove the appended child items from the end of the array
					items.splice(items.length - num, num);
					
					// Insert right after the clicked row!
					items.splice(clicked_index + 1, 0, ...new_rows);
					
					// Re-index all child items in the grid
					items.forEach((item, idx) => {
						item.idx = idx + 1;
					});
					
					frm.refresh_field('items');
					frappe.show_alert({message: __('{0} split rows added directly below.', [num]), color: 'green'});
				}
			}
		}, __('Split Row'), __('Split'));
	},
	item_code: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		if (row.item_code) {
			// Find the first populated row in the grid with this item_code to copy details from
			let match = frm.doc.items.find(d => d.item_code === row.item_code && d.name !== row.name && d.shipment);
			if (match) {
				frappe.model.set_value(cdt, cdn, 'shipment', match.shipment);
				frappe.model.set_value(cdt, cdn, 'item_name', match.item_name);
				frappe.model.set_value(cdt, cdn, 'description', match.description);
				frappe.model.set_value(cdt, cdn, 'total_qty', match.total_qty);
			}
		}
	},
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
			
			let max_qty = flt(row.total_qty);
			if (total > max_qty) {
				frappe.msgprint({
					title: __('Allocation Request Exceeded'),
					indicator: 'orange',
					message: __('Total Allocation Request for Item {0} is {1}, which exceeds the Shipment Quantity of {2}! Please reduce.', row.item_code, total, max_qty)
				});
			}
		}
	},
	final_allocation: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		if (row.item_code) {
			let final_total = 0;
			let quota = 0;
			frm.doc.items.forEach(function(item) {
				if (item.item_code === row.item_code) {
					final_total += flt(item.final_allocation);
					quota = Math.max(quota, flt(item.allocated_qty));
				}
			});
			if (final_total > quota) {
				frappe.msgprint({
					title: __('Quota Exceeded'),
					indicator: 'orange',
					message: __('Total Final Allocation for Item {0} is {1}, which exceeds the Quota of {2}! Please reduce.', row.item_code, final_total, quota)
				});
			}
		}
	}
});
