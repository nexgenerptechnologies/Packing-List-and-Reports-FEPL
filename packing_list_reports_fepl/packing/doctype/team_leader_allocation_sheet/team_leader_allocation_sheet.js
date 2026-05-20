// -*- coding: utf-8 -*-
// Copyright (c) 2026, Administrator and contributors
// For license information, please see license.txt

frappe.ui.form.on('Team Leader Allocation Sheet', {
	setup: function(frm) {
		frm.checked_partners = new Set();

		// Filter Shipment link inside shipments table to only show submitted Shipment Trackers
		frm.set_query('shipment_tracker', 'shipments', function() {
			return { filters: { docstatus: 1 } };
		});
	},

	refresh: function(frm) {
		frm.clear_custom_buttons();

		// Initialise checked_partners from items on first load
		let all_partners = new Set();
		(frm.doc.items || []).forEach(item => {
			if (item.sales_partner) all_partners.add(item.sales_partner);
		});

		if (!frm.checked_partners || frm.checked_partners.size === 0) {
			frm.checked_partners = new Set(all_partners);
		} else {
			frm.checked_partners.forEach(p => {
				if (!all_partners.has(p)) frm.checked_partners.delete(p);
			});
			all_partners.forEach(p => frm.checked_partners.add(p));
		}

		if (frm.doc.status === 'Draft') {
			// ── Fetch Partner Requests ──
			frm.add_custom_button(__('Fetch Partner Requests'), function() {
				frm.save().then(() => {
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
				});
			}).addClass('btn-primary');

			// ── Download Template ──
			frm.add_custom_button(__('Download Template'), function() {
				let url = '/api/method/packing_list_reports_fepl.packing.doctype.team_leader_allocation_sheet.team_leader_allocation_sheet.download_tl_template';
				if (!frm.is_new()) url += '?docname=' + frm.doc.name;
				window.open(url);
			});

			// ── Upload Excel Data ──
			if (frm.doc.excel_file) {
				frm.add_custom_button(__('Upload Excel Data'), function() {
					frm.save().then(() => {
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
					});
				}).addClass('btn-primary');
			}

			// ── Approve & Distribute ──
			if (frm.doc.items && frm.doc.items.length > 0) {
				frm.add_custom_button(__('Approve & Distribute Quotas'), function() {
					frappe.confirm(
						__('Are you sure you want to approve and distribute these quotas to all Sales Partners? This will update their individual sheets and move them to Partner Finalization stage.'),
						function() {
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

		// Apply filter & render dashboard
		frm.trigger('apply_partner_filter');
		frm.trigger('render_summary_dashboard');
	},

	// ─────────────────────────────────────────────────────────────────
	// apply_partner_filter – show / hide rows in the items grid
	// ─────────────────────────────────────────────────────────────────
	apply_partner_filter: function(frm) {
		let grid = frm.fields_dict['items'].grid;
		if (!grid || !grid.grid_rows) return;

		grid.grid_rows.forEach(row => {
			if (!row.doc.sales_partner || frm.checked_partners.has(row.doc.sales_partner)) {
				row.wrapper.show();
			} else {
				row.wrapper.hide();
			}
		});
	},

	// ─────────────────────────────────────────────────────────────────
	// render_summary_dashboard – full interactive HTML dashboard
	// ─────────────────────────────────────────────────────────────────
	render_summary_dashboard: function(frm) {

		// Safe float helper (avoids dependency on missing flt global)
		const _f = (v) => parseFloat(v) || 0;

		// ── Empty state ──
		if (!frm.doc.items || frm.doc.items.length === 0) {
			frm.set_df_property('summary_html', 'options', `
				<div style="padding:32px; text-align:center; background:#f9fafb; border-radius:12px; border:1px dashed #d1d5db;">
					<div style="font-size:36px; margin-bottom:10px;">&#x1F4CB;</div>
					<div style="font-size:15px; font-weight:700; color:#374151;">No Data Yet</div>
					<div style="font-size:13px; color:#6b7280; margin-top:6px;">
						Click <strong>Fetch Partner Requests</strong> to load partner allocation data.
					</div>
				</div>
			`);
			return;
		}

		// ── 1. Gather unique partners ──
		let all_partners = new Set();
		frm.doc.items.forEach(item => {
			if (item.sales_partner) all_partners.add(item.sales_partner);
		});
		let partners_array = Array.from(all_partners).sort();

		// ── 2. Assign a unique colour to each partner ──
		const PALETTE = ['#4f46e5','#0891b2','#059669','#d97706','#dc2626','#7c3aed','#db2777','#ea580c','#0f766e','#1d4ed8'];
		let partner_color = {};
		partners_array.forEach((p, i) => { partner_color[p] = PALETTE[i % PALETTE.length]; });

		// ── 3. Build toggle pills ──
		let partners_toggles = partners_array.map(p => {
			let active = frm.checked_partners.has(p);
			let bg     = active ? partner_color[p] : '#f3f4f6';
			let fg     = active ? '#ffffff' : '#374151';
			let border = active ? partner_color[p] : '#d1d5db';
			let mark   = active ? '&#x2713; ' : '';
			return `
				<label class="partner-toggle-pill" data-partner="${p}"
					style="display:inline-flex;align-items:center;gap:5px;cursor:pointer;
					background:${bg};color:${fg};border:1px solid ${border};
					padding:6px 14px;border-radius:20px;font-size:13px;font-weight:600;
					margin:4px;transition:all 0.18s;user-select:none;
					box-shadow:0 1px 3px rgba(0,0,0,0.08);">
					<input type="checkbox" data-partner="${p}" ${active ? 'checked' : ''} style="display:none;">
					<span>${mark}${p}</span>
				</label>`;
		}).join('');

		// ── 4. Consolidated totals (only checked partners) ──
		let consolidated = {};
		frm.doc.items.forEach(item => {
			if (!frm.checked_partners.has(item.sales_partner)) return;
			let code = item.item_code;
			if (!consolidated[code]) {
				consolidated[code] = {
					item_name:     item.item_name || '',
					shipment_qty:  _f(item.total_qty),
					requested_qty: 0,
					allocated_qty: 0
				};
			}
			consolidated[code].requested_qty += _f(item.allocation_request);
			consolidated[code].allocated_qty += _f(item.allocated_qty);
		});

		let grand_ship  = 0, grand_req = 0, grand_alloc = 0;
		let cons_rows = Object.entries(consolidated).map(([code, d]) => {
			grand_ship  += d.shipment_qty;
			grand_req   += d.requested_qty;
			grand_alloc += d.allocated_qty;
			let over_demand  = d.requested_qty > d.shipment_qty;
			let over_alloc   = d.allocated_qty > d.shipment_qty;
			let status_txt   = over_demand ? 'Over Demand' : 'OK';
			let status_bg    = over_demand ? '#fef2f2' : '#ecfdf5';
			let status_clr   = over_demand ? '#dc2626' : '#059669';
			return `
				<tr style="border-bottom:1px solid #f3f4f6;">
					<td style="padding:10px 12px;font-weight:700;color:#1f2937;font-size:13px;">${code}</td>
					<td style="padding:10px 12px;color:#374151;font-size:13px;">${d.item_name}</td>
					<td style="padding:10px 12px;text-align:right;font-weight:700;color:#059669;">${d.shipment_qty.toFixed(0)}</td>
					<td style="padding:10px 12px;text-align:right;font-weight:600;color:${over_demand ? '#dc2626' : '#1f2937'};">${d.requested_qty.toFixed(0)}</td>
					<td style="padding:10px 12px;text-align:right;font-weight:700;color:${over_alloc ? '#d97706' : '#4f46e5'};">${d.allocated_qty.toFixed(0)}</td>
					<td style="padding:10px 12px;text-align:center;">
						<span style="background:${status_bg};color:${status_clr};padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700;">${status_txt}</span>
					</td>
				</tr>`;
		}).join('');

		if (!cons_rows) {
			cons_rows = `<tr><td colspan="6" style="padding:24px;text-align:center;color:#9ca3af;font-style:italic;">No partners selected. Toggle the pills above to compare demand.</td></tr>`;
		}

		// ── 5. Per-partner breakdown ──
		let per_partner = {};
		frm.doc.items.forEach(item => {
			if (!frm.checked_partners.has(item.sales_partner)) return;
			let p    = item.sales_partner;
			let code = item.item_code;
			if (!per_partner[p]) per_partner[p] = {};
			if (!per_partner[p][code]) {
				per_partner[p][code] = {
					item_name:    item.item_name || '',
					shipment_qty: _f(item.total_qty),
					requested:    0,
					allocated:    0
				};
			}
			per_partner[p][code].requested += _f(item.allocation_request);
			per_partner[p][code].allocated += _f(item.allocated_qty);
		});

		let per_partner_html = partners_array
			.filter(p => per_partner[p])
			.map(p => {
				let color = partner_color[p];
				let items_data = per_partner[p];
				let tot_req   = Object.values(items_data).reduce((s, d) => s + d.requested, 0);
				let tot_alloc = Object.values(items_data).reduce((s, d) => s + d.allocated, 0);

				let rows = Object.entries(items_data).map(([code, d]) => {
					let over = d.requested > d.shipment_qty;
					return `
						<tr style="border-bottom:1px solid #f3f4f6;">
							<td style="padding:9px 12px;font-weight:700;color:#1f2937;font-size:12px;">${code}</td>
							<td style="padding:9px 12px;color:#374151;font-size:12px;">${d.item_name}</td>
							<td style="padding:9px 12px;text-align:right;color:#059669;font-weight:700;">${d.shipment_qty.toFixed(0)}</td>
							<td style="padding:9px 12px;text-align:right;color:${over ? '#dc2626' : '#374151'};font-weight:600;">${d.requested.toFixed(0)}</td>
							<td style="padding:9px 12px;text-align:right;color:#4f46e5;font-weight:700;">${d.allocated.toFixed(0)}</td>
						</tr>`;
				}).join('');

				return `
					<div style="margin-bottom:16px;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;box-shadow:0 2px 6px rgba(0,0,0,0.05);">
						<div style="background:${color};padding:12px 16px;display:flex;justify-content:space-between;align-items:center;">
							<div style="color:#fff;font-weight:800;font-size:14px;">&#x1F91D; ${p}</div>
							<div style="display:flex;gap:20px;">
								<div style="font-size:12px;color:rgba(255,255,255,0.85);">Requested: <strong style="color:#fff;">${tot_req.toFixed(0)}</strong></div>
								<div style="font-size:12px;color:rgba(255,255,255,0.85);">TL Quota: <strong style="color:#fff;">${tot_alloc.toFixed(0)}</strong></div>
							</div>
						</div>
						<table style="width:100%;border-collapse:collapse;">
							<thead>
								<tr style="background:#f9fafb;border-bottom:2px solid #e5e7eb;">
									<th style="padding:8px 12px;text-align:left;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;">Item Code</th>
									<th style="padding:8px 12px;text-align:left;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;">Item Name</th>
									<th style="padding:8px 12px;text-align:right;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;">Shipment Qty</th>
									<th style="padding:8px 12px;text-align:right;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;">Requested</th>
									<th style="padding:8px 12px;text-align:right;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;">TL Quota</th>
								</tr>
							</thead>
							<tbody>${rows}</tbody>
						</table>
					</div>`;
			}).join('');

		if (!per_partner_html) {
			per_partner_html = `<div style="padding:24px;text-align:center;color:#9ca3af;font-style:italic;">No partners selected.</div>`;
		}

		// ── 6. Assemble full dashboard HTML ──
		let html = `
			<style>
				.partner-toggle-pill:hover { transform:scale(1.05); box-shadow:0 4px 10px rgba(0,0,0,0.14) !important; }
				.partner-toggle-pill:active { transform:scale(0.97); }
				.tl-tab-btn {
					border:none; padding:8px 20px; border-radius:8px;
					font-size:13px; font-weight:700; cursor:pointer; transition:all 0.18s;
				}
				.tl-tab-btn.active { background:#4f46e5; color:#fff; box-shadow:0 2px 6px rgba(79,70,229,0.35); }
				.tl-tab-btn:not(.active) { background:#f3f4f6; color:#374151; }
				.tl-tab-btn:hover:not(.active) { background:#e5e7eb; }
				.tl-cons-table th {
					background:#f9fafb; color:#374151; font-weight:700; font-size:12px;
					text-transform:uppercase; letter-spacing:0.05em;
					padding:12px; border-bottom:2px solid #e5e7eb;
				}
				.tl-cons-table tr:hover { background:#fafafa; }
			</style>

			<div style="font-family:inherit; padding:4px 0;">

				<!-- Partner Pills Card -->
				<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin-bottom:16px;box-shadow:0 2px 6px rgba(0,0,0,0.05);">
					<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px;">
						<div style="font-size:12px;color:#6b7280;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;">
							&#x1F4CC; Select Partners to Compare
						</div>
						<div style="display:flex;gap:8px;align-items:center;">
							<span style="font-size:12px;color:#4f46e5;font-weight:700;background:#eef2ff;padding:4px 12px;border-radius:8px;">
								${frm.checked_partners.size} of ${partners_array.length} selected
							</span>
							<button class="btn-select-all-partners"
								style="background:#ecfdf5;border:none;color:#059669;font-size:12px;font-weight:700;cursor:pointer;padding:5px 12px;border-radius:8px;">
								&#x2713; Select All
							</button>
							<button class="btn-clear-all-partners"
								style="background:#fef2f2;border:none;color:#dc2626;font-size:12px;font-weight:700;cursor:pointer;padding:5px 12px;border-radius:8px;">
								&#x2715; Clear All
							</button>
						</div>
					</div>
					<div style="max-height:110px;overflow-y:auto;padding:2px 0;">
						${partners_toggles || '<span style="color:#9ca3af;font-style:italic;font-size:13px;">No partners yet. Click <strong>Fetch Partner Requests</strong> first.</span>'}
					</div>
				</div>

				<!-- Grand Totals Row -->
				<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;">
					<div style="flex:1;min-width:150px;background:#fff;border:1px solid #e5e7eb;border-left:4px solid #059669;border-radius:12px;padding:14px 16px;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
						<div style="font-size:11px;color:#6b7280;font-weight:700;text-transform:uppercase;">Shipment Capacity</div>
						<div style="font-size:28px;font-weight:800;color:#059669;margin-top:4px;">${grand_ship.toFixed(0)}</div>
						<div style="font-size:11px;color:#9ca3af;margin-top:2px;">Across selected partners</div>
					</div>
					<div style="flex:1;min-width:150px;background:#fff;border:1px solid #e5e7eb;border-left:4px solid ${grand_req > grand_ship ? '#dc2626' : '#f59e0b'};border-radius:12px;padding:14px 16px;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
						<div style="font-size:11px;color:#6b7280;font-weight:700;text-transform:uppercase;">Total Allocation Requested</div>
						<div style="font-size:28px;font-weight:800;color:${grand_req > grand_ship ? '#dc2626' : '#1f2937'};margin-top:4px;">${grand_req.toFixed(0)}</div>
						<div style="font-size:11px;color:#9ca3af;margin-top:2px;">${grand_req > grand_ship ? '&#x26A0;&#xFE0F; Exceeds capacity' : '&#x2713; Within capacity'}</div>
					</div>
					<div style="flex:1;min-width:150px;background:#fff;border:1px solid #e5e7eb;border-left:4px solid #4f46e5;border-radius:12px;padding:14px 16px;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
						<div style="font-size:11px;color:#6b7280;font-weight:700;text-transform:uppercase;">Total TL Quota Allocated</div>
						<div style="font-size:28px;font-weight:800;color:#4f46e5;margin-top:4px;">${grand_alloc.toFixed(0)}</div>
						<div style="font-size:11px;color:#9ca3af;margin-top:2px;">Across ${frm.checked_partners.size} partner(s)</div>
					</div>
					<div style="flex:1;min-width:150px;background:#fff;border:1px solid #e5e7eb;border-left:4px solid #d97706;border-radius:12px;padding:14px 16px;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
						<div style="font-size:11px;color:#6b7280;font-weight:700;text-transform:uppercase;">Partners Submitted</div>
						<div style="font-size:28px;font-weight:800;color:#d97706;margin-top:4px;">${partners_array.length}</div>
						<div style="font-size:11px;color:#9ca3af;margin-top:2px;">${frm.checked_partners.size} comparing now</div>
					</div>
				</div>

				<!-- Tab switcher -->
				<div style="display:flex;gap:8px;margin-bottom:14px;">
					<button class="tl-tab-btn active" data-tab="consolidated">&#x1F4CA; Consolidated View</button>
					<button class="tl-tab-btn" data-tab="per-partner">&#x1F465; Per Partner View</button>
				</div>

				<!-- Consolidated Table Panel -->
				<div class="tl-tab-panel" data-panel="consolidated"
					style="overflow-x:auto;background:#fff;border:1px solid #e5e7eb;border-radius:12px;box-shadow:0 2px 6px rgba(0,0,0,0.05);">
					<table class="tl-cons-table" style="width:100%;border-collapse:collapse;font-size:13px;text-align:left;">
						<thead>
							<tr>
								<th style="width:14%;padding:12px;">Item Code</th>
								<th style="width:26%;padding:12px;">Item Name</th>
								<th style="width:15%;padding:12px;text-align:right;">Shipment Capacity</th>
								<th style="width:15%;padding:12px;text-align:right;">Total Requested</th>
								<th style="width:15%;padding:12px;text-align:right;">Total TL Quota</th>
								<th style="width:15%;padding:12px;text-align:center;">Status</th>
							</tr>
						</thead>
						<tbody>${cons_rows}</tbody>
					</table>
				</div>

				<!-- Per-Partner Panel (hidden by default) -->
				<div class="tl-tab-panel" data-panel="per-partner" style="display:none;">
					${per_partner_html}
				</div>

			</div>`;

		frm.set_df_property('summary_html', 'options', html);

		// ── 7. Attach interactive events after DOM paint ──
		setTimeout(() => {
			let $w = frm.fields_dict['summary_html'].$wrapper;
			if (!$w || !$w.length) return;

			// Toggle a partner pill
			$w.off('click', '.partner-toggle-pill').on('click', '.partner-toggle-pill', function(e) {
				e.preventDefault();
				let p = $(this).attr('data-partner');
				if (frm.checked_partners.has(p)) {
					frm.checked_partners.delete(p);
				} else {
					frm.checked_partners.add(p);
				}
				frm.trigger('apply_partner_filter');
				frm.trigger('render_summary_dashboard');
			});

			// Select All
			$w.off('click', '.btn-select-all-partners').on('click', '.btn-select-all-partners', function(e) {
				e.preventDefault();
				partners_array.forEach(p => frm.checked_partners.add(p));
				frm.trigger('apply_partner_filter');
				frm.trigger('render_summary_dashboard');
			});

			// Clear All
			$w.off('click', '.btn-clear-all-partners').on('click', '.btn-clear-all-partners', function(e) {
				e.preventDefault();
				frm.checked_partners.clear();
				frm.trigger('apply_partner_filter');
				frm.trigger('render_summary_dashboard');
			});

			// Tab switching
			$w.off('click', '.tl-tab-btn').on('click', '.tl-tab-btn', function(e) {
				e.preventDefault();
				let tab = $(this).attr('data-tab');
				$w.find('.tl-tab-btn').removeClass('active');
				$(this).addClass('active');
				$w.find('.tl-tab-panel').hide();
				$w.find(`.tl-tab-panel[data-panel="${tab}"]`).show();
			});

		}, 150);
	}
});

// ── Re-render dashboard when TL Quota is edited inline ──
frappe.ui.form.on('Team Leader Allocation Detail', {
	allocated_qty: function(frm) {
		frm.trigger('render_summary_dashboard');
	},
	items_add: function(frm) {
		frm.trigger('render_summary_dashboard');
	},
	items_remove: function(frm) {
		frm.trigger('render_summary_dashboard');
	}
});

// ── Auto-fill Supplier / ETD / ETA when a Shipment Tracker row is picked ──
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
