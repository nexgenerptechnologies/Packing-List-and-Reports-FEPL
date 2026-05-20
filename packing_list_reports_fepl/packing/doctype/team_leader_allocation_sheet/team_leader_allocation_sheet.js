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
			frm.set_df_property('sales_partner_filter', 'read_only', 1);
			items_grid.update_docfield_property('allocated_qty', 'read_only', 1);
		} else {
			frm.set_df_property('shipments', 'read_only', 0);
			frm.set_df_property('excel_file', 'read_only', 0);
			frm.set_df_property('sales_partner_filter', 'read_only', 0);
			items_grid.update_docfield_property('allocated_qty', 'read_only', 0);
		}

		// Apply dynamic grid filter & render dashboard
		frm.trigger('apply_partner_filter');
		frm.trigger('render_summary_dashboard');
	},

	sales_partner_filter: function(frm) {
		frm.trigger('apply_partner_filter');
	},

	apply_partner_filter: function(frm) {
		let filter_partner = frm.doc.sales_partner_filter;
		let grid = frm.fields_dict['items'].grid;
		
		if (!grid || !grid.grid_rows) return;
		
		grid.grid_rows.forEach(row => {
			if (!filter_partner || row.doc.sales_partner === filter_partner) {
				row.wrapper.show();
			} else {
				row.wrapper.hide();
			}
		});
	},

	render_summary_dashboard: function(frm) {
		if (!frm.doc.items || frm.doc.items.length === 0) {
			frm.set_df_property('summary_html', 'options', `
				<div style="padding: 20px; text-align: center; color: #888; font-style: italic; background: #f9f9f9; border-radius: 8px; border: 1px dashed #ddd;">
					No partner allocation requests fetched yet. Click "Fetch Partner Requests" to load data.
				</div>
			`);
			return;
		}

		// 1. Compute stats
		let unique_partners = new Set();
		let item_consolidated = {}; // item_code -> { item_name, total_qty, requested, allocated }

		frm.doc.items.forEach(item => {
			if (item.sales_partner) {
				unique_partners.add(item.sales_partner);
			}
			
			let code = item.item_code;
			if (!item_consolidated[code]) {
				item_consolidated[code] = {
					item_name: item.item_name || "",
					shipment_qty: flt(item.total_qty),
					requested_qty: 0.0,
					allocated_qty: 0.0
				};
			}
			item_consolidated[code].requested_qty += flt(item.allocation_request);
			item_consolidated[code].allocated_qty += flt(item.allocated_qty);
		});

		let partners_list = Array.from(unique_partners);
		let partners_badges = partners_list.map(p => `
			<span style="display: inline-block; background: #eef2ff; color: #4f46e5; border: 1px solid #c7d2fe; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 500; margin: 4px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
				${p}
			</span>
		`).join('');

		// Build table rows
		let table_rows = "";
		Object.keys(item_consolidated).forEach(code => {
			let item = item_consolidated[code];
			let is_excess = item.requested_qty > item.shipment_qty;
			let is_allocated_excess = item.allocated_qty > item.shipment_qty;
			
			let status_badge = "";
			if (is_excess) {
				status_badge = `<span style="background: #fef2f2; color: #dc2626; border: 1px solid #fca5a5; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: bold; display: inline-flex; align-items: center; gap: 4px; animation: pulse 2s infinite;">
					⚠️ EXCESS REQUESTED
				</span>`;
			} else {
				status_badge = `<span style="background: #ecfdf5; color: #059669; border: 1px solid #6ee7b7; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: bold;">
					✓ OK
				</span>`;
			}

			if (is_allocated_excess) {
				status_badge += ` <span style="background: #fffbeb; color: #d97706; border: 1px solid #fcd34d; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: bold; margin-left: 5px;">
					⚠️ OVER-ALLOCATED
				</span>`;
			}

			table_rows += `
				<tr style="border-bottom: 1px solid #f3f4f6; transition: background 0.2s;">
					<td style="padding: 12px; font-weight: 600; color: #1f2937;">${code}</td>
					<td style="padding: 12px; color: #4b5563;">${item.item_name}</td>
					<td style="padding: 12px; text-align: right; font-weight: 500; color: #059669;">${item.shipment_qty}</td>
					<td style="padding: 12px; text-align: right; font-weight: 500; color: ${is_excess ? '#dc2626' : '#1f2937'};">${item.requested_qty}</td>
					<td style="padding: 12px; text-align: right; font-weight: 600; color: ${is_allocated_excess ? '#d97706' : '#4f46e5'};">${item.allocated_qty}</td>
					<td style="padding: 12px; text-align: center;">${status_badge}</td>
				</tr>
			`;
		});

		// Build overall CSS and layout
		let dashboard_html = `
			<style>
				@keyframes pulse {
					0% { opacity: 1; }
					50% { opacity: 0.6; }
					100% { opacity: 1; }
				}
				.tl-card-stat {
					background: #ffffff;
					border: 1px solid #e5e7eb;
					border-radius: 12px;
					padding: 16px;
					box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03);
					flex: 1;
					min-width: 220px;
					transition: transform 0.2s, box-shadow 0.2s;
				}
				.tl-card-stat:hover {
					transform: translateY(-2px);
					box-shadow: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -2px rgba(0,0,0,0.05);
				}
				.tl-table th {
					background: #f9fafb;
					color: #374151;
					font-weight: 600;
					font-size: 12px;
					text-transform: uppercase;
					letter-spacing: 0.05em;
					padding: 12px;
					border-bottom: 2px solid #e5e7eb;
				}
				.tl-table tr:hover {
					background: #f9fafb;
				}
			</style>
			
			<div style="font-family: inherit;">
				<!-- Stats Row -->
				<div style="display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 20px;">
					
					<!-- Card 1: Partners Count -->
					<div class="tl-card-stat" style="border-left: 4px solid #4f46e5;">
						<div style="font-size: 12px; color: #6b7280; font-weight: 600; text-transform: uppercase;">Submitted Partners</div>
						<div style="font-size: 32px; font-weight: 800; color: #4f46e5; margin: 8px 0 4px 0; display: flex; align-items: center; gap: 8px;">
							${partners_list.length}
							<span style="font-size: 13px; font-weight: 500; color: #10b981; background: #ecfdf5; padding: 2px 8px; border-radius: 12px;">Active</span>
						</div>
						<div style="font-size: 12px; color: #9ca3af;">All pending partner sheets analyzed</div>
					</div>

					<!-- Card 2: Partners List -->
					<div class="tl-card-stat" style="border-left: 4px solid #10b981; flex: 2;">
						<div style="font-size: 12px; color: #6b7280; font-weight: 600; text-transform: uppercase;">Partners List</div>
						<div style="margin-top: 10px; max-height: 70px; overflow-y: auto;">
							${partners_badges || '<span style="color:#9ca3af; font-style:italic; font-size:13px;">No partners submitted yet</span>'}
						</div>
					</div>

				</div>

				<!-- Consolidated / Clubbed View Header -->
				<div style="margin-top: 24px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
					<h5 style="margin: 0; font-size: 14px; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 0.05em; display: flex; align-items: center; gap: 6px;">
						<span style="background: #4f46e5; width: 4px; height: 16px; display: inline-block; border-radius: 2px;"></span>
						Consolidated Demand vs Shipment Capacity (Clubbed View)
					</h5>
					<span style="font-size: 12px; color: #6b7280; font-style: italic;">
						Combined across all submitted partner requests
					</span>
				</div>

				<!-- Consolidated Table -->
				<div style="overflow-x: auto; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
					<table class="tl-table" style="width: 100%; border-collapse: collapse; text-align: left; font-size: 13px;">
						<thead>
							<tr>
								<th style="width: 15%; padding: 12px;">Item Code</th>
								<th style="width: 25%; padding: 12px;">Item Name</th>
								<th style="width: 15%; padding: 12px; text-align: right;">Shipment Capacity</th>
								<th style="width: 15%; padding: 12px; text-align: right;">Total Requested</th>
								<th style="width: 15%; padding: 12px; text-align: right;">Total Allocated (TL Quota)</th>
								<th style="width: 15%; padding: 12px; text-align: center;">Status</th>
							</tr>
						</thead>
						<tbody>
							${table_rows}
						</tbody>
					</table>
				</div>
			</div>
		`;

		frm.set_df_property('summary_html', 'options', dashboard_html);
	}
});

// Update summary html dynamically when a TL Quota is modified in the child table!
frappe.ui.form.on('Team Leader Allocation Detail', {
	allocated_qty: function(frm, cdt, cdn) {
		frm.trigger('render_summary_dashboard');
	},
	items_add: function(frm, cdt, cdn) {
		frm.trigger('render_summary_dashboard');
	},
	items_remove: function(frm, cdt, cdn) {
		frm.trigger('render_summary_dashboard');
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
