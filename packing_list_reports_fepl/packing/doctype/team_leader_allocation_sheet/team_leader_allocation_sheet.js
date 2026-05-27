// Copyright (c) 2026, Administrator and contributors
// For license information, please see license.txt

frappe.ui.form.on('Team Leader Allocation Sheet', {
	onload: function(frm) {
		if (frm.doc.excel_file) {
			frm.trigger('refresh');
		}
	},
	setup: function(frm) {
		frm.set_query('shipment_tracker', 'shipments', function(doc) {
			return {
				query: "packing_list_reports_fepl.packing.doctype.team_leader_allocation_sheet.team_leader_allocation_sheet.get_available_shipments_for_tl",
				filters: {
					current_sheet: doc.name
				}
			};
		});
	},

	refresh: function(frm) {
		frappe.db.get_single_value('Packing List Settings', 'enable_team_leader_allocation_sheet').then(val => {
			if (val === 0 || val === '0') {
				frappe.msgprint({
					title: __('Feature Disabled'),
					indicator: 'red',
					message: __('Team Leader Allocation Sheet is disabled. Click <a href=/app/packing-list-settings>here</a> to go to Settings and enable it.')
				});
				frm.disable_save();
			}
		});
		frm.clear_custom_buttons();

		// Keep the dashboard section visible for our custom matrix grid
		frm.toggle_display('summary_html_section', true);

		if (frm.doc.status === 'Draft') {
			// Fetch Partner Requests
			frm.add_custom_button(__('Fetch Partner Requests'), function() {
				let action = () => {
					frappe.call({
						method: 'packing_list_reports_fepl.packing.doctype.team_leader_allocation_sheet.team_leader_allocation_sheet.fetch_partner_requests',
						args: { docname: frm.doc.name },
						callback: function(r) {
							if (!r.exc) {
								frappe.show_alert({ message: __(r.message), indicator: 'green' });
								frm.reload_doc();
							}
						}
					});
				};
				if (frm.is_dirty()) {
					frm.save(null, action);
				} else {
					action();
				}
			}).addClass('btn-primary');

			// Download Template
			frm.add_custom_button(__('Download Request Template'), function() {
				let url = '/api/method/packing_list_reports_fepl.packing.doctype.team_leader_allocation_sheet.team_leader_allocation_sheet.download_tl_request_template';
				if (!frm.is_new()) url += '?docname=' + frm.doc.name;
				window.open(url);
			}, __('Download Template'));

			frm.add_custom_button(__('Download Matrix Template'), function() {
				let url = '/api/method/packing_list_reports_fepl.packing.doctype.team_leader_allocation_sheet.team_leader_allocation_sheet.download_tl_template';
				if (!frm.is_new()) url += '?docname=' + frm.doc.name;
				window.open(url);
			}, __('Download Template'));

			// Upload Excel Data
			if (frm.doc.excel_file) {
				frm.add_custom_button(__('Upload Excel Data'), function() {
					let action = () => {
						frappe.call({
							method: 'packing_list_reports_fepl.packing.doctype.team_leader_allocation_sheet.team_leader_allocation_sheet.upload_tl_excel',
							args: { docname: frm.doc.name },
							callback: function(r) {
								if (!r.exc) {
									frappe.show_alert({ message: __(r.message), indicator: 'green' });
									frm.reload_doc();
								}
							}
						});
					};
					if (frm.is_dirty()) {
						frm.save(null, action);
					} else {
						action();
					}
				}).addClass('btn-primary');
			}

			// Approve & Distribute
			if (frm.doc.items && frm.doc.items.length > 0) {
				frm.add_custom_button(__('Approve & Distribute Quotas'), function() {
					frappe.confirm(
						__('Are you sure you want to approve and distribute these quotas to all Sales Partners? This will update their individual sheets and move them to Partner Finalization stage.'),
						function() {
							let approve_action = function() {
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
							};
							if (frm.is_dirty()) {
								frm.save(null, approve_action);
							} else {
								approve_action();
							}
						}
					);
				}).addClass('btn-success');
			}
		}

		// Read-only rules
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

		// Render the custom Interactive Allocation Matrix Grid
		render_allocation_matrix(frm);
	}
});

// Auto-fill Supplier / ETD / ETA when a Shipment Tracker row is picked
frappe.ui.form.on('Item Allocation Shipment', {
	shipment_tracker: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		if (!row.shipment_tracker) return;
		frappe.call({
			method: 'frappe.client.get',
			args: { doctype: 'Shipment Tracker', name: row.shipment_tracker },
			callback: function(r) {
				if (r.message) {
					frappe.model.set_value(cdt, cdn, 'supplier', r.message.supplier);
					frappe.model.set_value(cdt, cdn, 'etd',      r.message.etd);
					frappe.model.set_value(cdt, cdn, 'eta',      r.message.eta);
				}
			}
		});
	}
});

function render_allocation_matrix(frm) {
	let wrapper = $(frm.fields_dict['summary_html'].wrapper);
	wrapper.empty();

	if (!frm.doc.items || frm.doc.items.length === 0) {
		wrapper.html(`
			<div style="text-align: center; padding: 40px 20px; color: #8a96a3; border: 1px dashed var(--border-color); border-radius: 8px; margin: 15px 0; background: var(--card-bg);">
				<p style="font-size: 16px; font-weight: 600; margin-bottom: 8px; color: var(--text-color);">No Partner Requests Loaded</p>
				<p style="font-size: 13px; margin: 0;">Select shipments above and click <strong>Fetch Partner Requests</strong> to populate the allocation matrix.</p>
			</div>
		`);
		return;
	}

	// Extract unique item codes to pass directly
	let item_codes = [];
	frm.doc.items.forEach(item => {
		if (item.item_code && !item_codes.includes(item.item_code)) {
			item_codes.push(item.item_code);
		}
	});

	// Fetch SPQs and active Sales Partners from master first
	frappe.call({
		method: 'packing_list_reports_fepl.packing.doctype.team_leader_allocation_sheet.team_leader_allocation_sheet.get_item_spqs',
		args: {
			docname: frm.doc.name,
			item_codes: item_codes
		},
		callback: function(r) {
			let spq_cache = r.message.spqs || {};
			let all_active_partners = r.message.partners || [];
			build_matrix_html(frm, wrapper, spq_cache, all_active_partners);
		}
	});
}

function build_matrix_html(frm, wrapper, spq_cache, all_active_partners) {
	let partner_display_map = {};
	let all_partners = [];
	
	if (all_active_partners && all_active_partners.length > 0) {
		all_active_partners.forEach(p => {
			all_partners.push(p.name);
			partner_display_map[p.name] = p.sales_partner_name || p.name;
		});
	} else {
		frm.doc.items.forEach(item => {
			if (!item.item_code) return;
			if (item.sales_partner && !all_partners.includes(item.sales_partner)) {
				all_partners.push(item.sales_partner);
				partner_display_map[item.sales_partner] = item.sales_partner;
			}
		});
	}
	all_partners.sort();

	let items_by_code = {};

	frm.doc.items.forEach(item => {
		if (!item.item_code) return;
		let key = item.item_code;
		if (!items_by_code[key]) {
			items_by_code[key] = {
				item_code: item.item_code,
				item_name: item.item_name || "",
				description: item.description || "",
				total_qty: item.total_qty || 0,
				spq: spq_cache[item.item_code] || 1,
				partners: {},
				total_req: 0,
				total_quota: 0
			};
		}
		let p = item.sales_partner;
		if (!items_by_code[key].partners[p]) {
			items_by_code[key].partners[p] = {
				allocation_request: 0,
				allocated_qty: 0,
				rows: []
			};
		}
		items_by_code[key].partners[p].allocation_request += item.allocation_request || 0;
		// Instead of summing across split rows, the allocated quota is the uniform value stored in the row!
		items_by_code[key].partners[p].allocated_qty = item.allocated_qty || 0;
		items_by_code[key].partners[p].rows.push(item);
		
		items_by_code[key].total_req += item.allocation_request || 0;
	});

	let style_html = `
		<style>
			.matrix-table {
				width: 100%;
				border-collapse: collapse;
				font-size: 12px;
				margin-top: 10px;
			}
			.matrix-table th {
				background: var(--bg-light-gray);
				font-weight: 600;
				color: var(--text-color);
				padding: 10px 8px;
				border: 1px solid var(--border-color);
				text-align: center;
				white-space: nowrap;
			}
			.matrix-table td {
				padding: 8px;
				border: 1px solid var(--border-color);
				vertical-align: middle;
				color: var(--text-color);
			}
			.matrix-sticky-col {
				position: sticky;
				left: 0;
				background: var(--card-bg) !important;
				z-index: 1;
				box-shadow: 2px 0 5px rgba(0,0,0,0.05);
			}
			.matrix-quota-input {
				padding: 4px 6px;
				font-size: 12px;
				height: 28px;
				text-align: right;
				width: 100%;
				max-width: 110px;
				border-radius: 4px;
				border: 1px solid var(--border-color);
				background: var(--bg-color);
				font-weight: 500;
				color: var(--text-color);
				transition: border-color 0.2s;
			}
			.matrix-quota-input:focus {
				border-color: var(--primary);
				outline: none;
				box-shadow: 0 0 0 2px rgba(31, 73, 125, 0.15);
			}
			.matrix-quota-input:disabled {
				background: var(--bg-light-gray);
				cursor: not-allowed;
			}
			.req-label {
				font-size: 10px;
				color: var(--text-muted);
				margin-bottom: 2px;
				text-align: right;
			}
			.warning-badge {
				background: #fdf2f2;
				color: #d9534f;
				border: 1px solid #f5c6cb;
				border-radius: 4px;
				padding: 2px 6px;
				font-weight: 600;
				font-size: 11px;
				display: inline-block;
			}
		</style>
	`;

	let table_html = style_html + `
		<div class="matrix-container" style="margin: 15px 0;">
			<h4 style="margin-bottom: 12px; font-weight: 600; color: var(--text-color);">Interactive Allocation Matrix</h4>
			<p class="text-muted" style="font-size: 13px; margin-bottom: 15px;">
				Use this grid to allocate quotas to each Sales Partner. Any modifications here immediately update the requests list in real time.
			</p>
			<div style="overflow-x: auto; border: 1px solid var(--border-color); border-radius: 8px; background: var(--card-bg);">
				<table class="table table-bordered matrix-table" style="margin: 0; min-width: 1000px;">
					<thead>
						<tr>
							<th class="matrix-sticky-col" style="text-align: left; width: 120px;">Item Code</th>
							<th style="text-align: left; width: 150px;">Item Name</th>
							<th style="text-align: left; max-width: 200px;">Description</th>
							<th style="text-align: right; width: 95px;">Shipment Qty</th>
							<th style="text-align: center; width: 65px;">SPQ</th>
							${all_partners.map(p => `
								<th style="background: rgba(31, 73, 125, 0.04); min-width: 110px;">${partner_display_map[p] || p}</th>
							`).join("")}
							<th style="text-align: right; width: 100px; background: #FFF9E6;">Total Request</th>
							<th style="text-align: right; width: 110px;">Remaining Qty</th>
						</tr>
					</thead>
					<tbody>
	`;

	Object.keys(items_by_code).forEach(key => {
		let details = items_by_code[key];
		let item_code = details.item_code;
		
		// Sum unique quota per Sales Partner to find total allocated quota for this item code
		let total_allocated_for_item = 0;
		let partner_quotas = {};
		frm.doc.items.forEach(child => {
			if (child.item_code === item_code && child.sales_partner) {
				partner_quotas[child.sales_partner] = child.allocated_qty || 0;
			}
		});
		Object.values(partner_quotas).forEach(q => {
			total_allocated_for_item += q;
		});
		
		let remaining_qty = details.total_qty - total_allocated_for_item;
		let is_over = total_allocated_for_item > details.total_qty;

		table_html += `
			<tr data-key="${key}" data-item-code="${item_code}">
				<td class="matrix-sticky-col" style="font-weight: 600;">${item_code}</td>
				<td style="font-weight: 500;">${details.item_name}</td>
				<td style="font-size: 11px; color: var(--text-muted); max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${details.description}">${details.description}</td>
				<td style="text-align: right; font-weight: 500;">${frappe.format(details.total_qty, {fieldtype: "Float"}, {only_value: true})}</td>
				<td style="text-align: center; color: #555; font-weight: 500;">${details.spq}</td>
				
				<!-- Partners -->
				${all_partners.map(p => {
					let partner_data = details.partners[p];
					if (partner_data) {
						let row_names = partner_data.rows.map(r => r.name).join(",");
						return `
							<td style="background: rgba(31, 73, 125, 0.01); text-align: center; vertical-align: middle;">
								<div class="req-label">Req: ${frappe.format(partner_data.allocation_request, {fieldtype: "Float"}, {only_value: true})}</div>
								<input type="number" 
									class="matrix-quota-input" 
									data-row-names="${row_names}" 
									data-item-code="${item_code}"
									data-partner="${p}"
									value="${partner_data.allocated_qty || 0}" 
									step="${details.spq}"
									${frm.doc.status === "Approved" ? "disabled" : ""}>
							</td>
						`;
					} else {
						return `
							<td style="background: rgba(31, 73, 125, 0.01); text-align: center; vertical-align: middle;">
								<div class="req-label">Req: 0.00</div>
								<input type="number" 
									class="matrix-quota-input" 
									data-row-names="" 
									data-item-code="${item_code}"
									data-partner="${p}"
									value="0" 
									step="${details.spq}"
									${frm.doc.status === "Approved" ? "disabled" : ""}>
							</td>
						`;
					}
				}).join("")}
				
				<td style="text-align: right; background: #FFF9E6; font-weight: 500;">${frappe.format(details.total_req, {fieldtype: "Float"}, {only_value: true})}</td>
				<td class="remaining-qty-cell" style="text-align: right; font-weight: 600; color: ${is_over ? "#d9534f" : "#2e7d32"}; background: ${is_over ? "#fdf2f2" : "#f4faf6"};" data-item-code="${item_code}" data-total-qty="${details.total_qty}">
					${frappe.format(remaining_qty, {fieldtype: "Float"}, {only_value: true})}
				</td>
			</tr>
		`;
	});

	table_html += `
					</tbody>
				</table>
			</div>
		</div>
	`;

	wrapper.html(table_html);

	// Zero-lag focus-preserving live updates
	wrapper.off("input", ".matrix-quota-input");
	wrapper.on("input", ".matrix-quota-input", function() {
		let input = $(this);
		let item_code = input.data("item-code");
		
		let total_quota = 0;
		wrapper.find(`.matrix-quota-input[data-item-code="${item_code}"]`).each(function() {
			total_quota += parseFloat($(this).val()) || 0;
		});
		
		let rem_cells = wrapper.find(`.remaining-qty-cell[data-item-code="${item_code}"]`);
		let shipment_qty = parseFloat(rem_cells.first().data("total-qty")) || 0;
		let remaining_qty = shipment_qty - total_quota;
		
		rem_cells.text(frappe.format(remaining_qty, {fieldtype: "Float"}, {only_value: true}));
		
		if (remaining_qty < 0) {
			rem_cells.css({
				"color": "#d9534f",
				"background": "#fdf2f2"
			});
		} else {
			rem_cells.css({
				"color": "#2e7d32",
				"background": "#f4faf6"
			});
		}
	});

	// Write to underlying model on change (blur / focus loss)
	wrapper.off("change", ".matrix-quota-input");
	wrapper.on("change", ".matrix-quota-input", function() {
		let input = $(this);
		let row_names_str = input.data("row-names");
		let val = parseFloat(input.val()) || 0;
		
		if (row_names_str) {
			let row_names = row_names_str.split(",");
			// Write the full allocated quota to all matching split rows in the child table (NO division or distribution!)
			row_names.forEach(r_name => {
				frappe.model.set_value("Team Leader Allocation Detail", r_name, "allocated_qty", val);
			});
		} else if (val > 0) {
			// No existing child row for this item and partner. Let's create one dynamically!
			let item_code = input.data("item-code");
			let partner = input.data("partner");
			
			// Find an existing child row of the same item code to copy shipment, item_name, description, total_qty, customer
			let copy_template = null;
			frm.doc.items.forEach(child => {
				if (child.item_code === item_code) {
					copy_template = child;
				}
			});
			
			if (copy_template) {
				let child = frm.add_child("items");
				child.shipment = copy_template.shipment;
				child.item_code = copy_template.item_code;
				child.item_name = copy_template.item_name;
				child.description = copy_template.description;
				child.total_qty = copy_template.total_qty;
				child.sales_partner = partner;
				child.customer = copy_template.customer;
				child.allocation_request = 0.0;
				child.allocated_qty = val;
				
				frm.refresh_field("items");
				render_allocation_matrix(frm);
			}
		}
	});
}