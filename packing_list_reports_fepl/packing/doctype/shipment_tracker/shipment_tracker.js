frappe.ui.form.on('Shipment Tracker', {
	validate: function(frm) {
		let invoice_dates = {};
		let conflicting = [];

		(frm.doc.shipment_items || []).forEach(item => {
			if (item.supplier_invoice && item.bill_date) {
				let inv = item.supplier_invoice.trim().toLowerCase();
				let date = item.bill_date;
				if (invoice_dates[inv] && invoice_dates[inv] !== date) {
					conflicting.push(__('Supplier Invoice # "{0}" has conflicting Invoice Dates in this tracker ({1} vs {2}).', [item.supplier_invoice, invoice_dates[inv], date]));
				}
				invoice_dates[inv] = date;
			}
		});

		if (conflicting.length > 0) {
			frappe.msgprint({
				title: __('Validation Error'),
				indicator: 'red',
				message: conflicting.join('<br>')
			});
			frappe.validated = false;
			return;
		}
	},
	refresh: function(frm) {
		frappe.db.get_single_value('Packing List Settings', 'enable_shipment_tracker').then(val => {
			if (val === 0 || val === '0') {
				frappe.msgprint({
					title: __('Feature Disabled'),
					indicator: 'red',
					message: __('Shipment Tracker is disabled. Click <a href=/app/packing-list-settings>here</a> to go to Settings and enable it.')
				});
				frm.disable_save();
			}
		});
		frm.clear_custom_buttons();
		
		frm.add_custom_button(__('Download Template'), function() {
			if (frm.is_dirty() && frm.doc.shipment_items && frm.doc.shipment_items.length > 0) {
				frappe.confirm(__('You have unsaved items in the table. To download a pre-filled template, please save the document first. Would you like to save now?'), function() {
					frm.save().then(() => {
						window.open('/api/method/packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.download_template?docname=' + encodeURIComponent(frm.doc.name));
					});
				}, function() {
					window.open('/api/method/packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.download_template');
				});
			} else {
				let url = '/api/method/packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.download_template';
				if (frm.doc.name && frm.doc.shipment_items && frm.doc.shipment_items.length > 0) {
					url += '?docname=' + encodeURIComponent(frm.doc.name);
				}
				window.open(url);
			}
		});

		if (frm.doc.docstatus === 0 && frm.doc.supplier && frm.doc.shipment_pos && frm.doc.shipment_pos.length > 0) {
			frm.add_custom_button(__('Fetch Pending Orders'), function() {
				frm.events.fetch_pending_items(frm);
			}).addClass('btn-primary');
		}
		
		if (frm.doc.docstatus === 0 && frm.doc.excel_file) {
			frm.add_custom_button(__('Fetch from Excel'), function() {
				let call_fetch = function(auto_update = 0) {
					frappe.call({
						method: "packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.fetch_from_excel",
						args: { docname: frm.doc.name, auto_update_rates: auto_update },
						freeze: true,
						freeze_message: __("Processing..."),
						callback: function(r) {
							if (!r.exc && r.message) {
								if (r.message.status === "Success") {
									frappe.show_alert({message: __('Excel data loaded successfully.'), color: 'green'});
									frm.reload_doc();
								} else if (r.message.status === "rate_mismatch") {
									let data = r.message.data;
									
									let rows_html = "";
									let has_updatable = false;
									data.forEach(d => {
										let status_html = d.can_update 
											? `<span class="text-success" style="font-weight:bold;">Ready to Update</span>` 
											: `<span class="text-danger" style="font-weight:bold;">Blocked: Already Received</span>`;
										if (d.can_update) has_updatable = true;
											
										rows_html += `
											<tr>
												<td>${d.po_number}</td>
												<td>${d.item_code}</td>
												<td class="text-right">${format_currency(d.old_rate)}</td>
												<td class="text-right">${format_currency(d.new_rate)}</td>
												<td>${status_html}</td>
											</tr>
										`;
									});
									
									let html = `
										<p>The following items in your Excel file have different rates compared to their Purchase Orders:</p>
										<div style="max-height: 300px; overflow-y: auto;">
											<table class="table table-bordered">
												<thead>
													<tr>
														<th>PO Number</th>
														<th>Item Code</th>
														<th class="text-right">PO Rate</th>
														<th class="text-right">Excel Rate</th>
														<th>Status</th>
													</tr>
												</thead>
												<tbody>
													${rows_html}
												</tbody>
											</table>
										</div>
									`;
									
									if (has_updatable) {
										html += `<p class="mt-3"><b>Do you want to automatically update the eligible Purchase Orders with the new Excel rates?</b></p>`;
									} else {
										html += `<p class="mt-3 text-danger"><b>None of the items can be updated because they are already received. Please correct your Excel file.</b></p>`;
									}
									
									let d = new frappe.ui.Dialog({
										title: __('Rate Mismatch Detected'),
										fields: [{ fieldtype: 'HTML', fieldname: 'html_table', options: html }],
										primary_action_label: has_updatable ? __('Update Eligible Rates & Proceed') : __('Close'),
										primary_action: function() {
											d.hide();
											if (has_updatable) {
												call_fetch(1);
											}
										},
										secondary_action_label: __('Cancel'),
										secondary_action: function() {
											d.hide();
										}
									});
									d.show();
								}
							}
						}
					});
				};
				call_fetch(0);
			}).addClass('btn-primary');
		}
		
		if (frm.doc.docstatus === 1 && !frm.doc.purchase_receipt) {
			frm.add_custom_button(__('Create Purchase Receipt'), function() {
				frm.events.make_purchase_receipt(frm);
			}).addClass('btn-primary');
		}
		
		if (frm.doc.docstatus === 1 && frm.doc.purchase_receipt) {
			frappe.call({
				method: "packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.has_purchase_invoices",
				args: { purchase_receipt: frm.doc.purchase_receipt },
				callback: function(r) {
					if (!r.message) {
						frm.add_custom_button(__('Create Purchase Invoices'), function() {
							frm.events.create_purchase_invoices(frm);
						}).addClass('btn-primary');
					}
				}
			});
		}

		frm.add_custom_button(__('Add Remark'), function() {
			frappe.prompt({
				label: __('Remark'),
				fieldname: 'remark',
				fieldtype: 'Small Text',
				reqd: 1
			}, (values) => {
				frappe.call({
					method: "packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.add_shipment_remark",
					args: {
						docname: frm.doc.name,
						remark: values.remark
					},
					freeze: true,
					callback: function(r) {
						if (!r.exc) {
							frappe.show_alert({message: __('Remark added successfully.'), color: 'green'});
							frm.reload_doc();
						}
					}
				});
			}, __('Add Remark to Timeline'), __('Add'));
		}, __('Actions'));
	},

	fetch_pending_items: function(frm) {
		frappe.call({
			method: "packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.fetch_pending_items",
			args: { docname: frm.doc.name },
			callback: function(r) {
				if (!r.exc) {
					frappe.show_alert({message: __('Pending items fetched successfully.'), color: 'green'});
					frm.reload_doc();
				}
			}
		});
	},

	make_purchase_receipt: function(frm) {
		frappe.confirm(__('Are you sure you want to create a Purchase Receipt?'), function() {
			frappe.call({
				method: "packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.make_purchase_receipt",
				args: { docname: frm.doc.name },
				freeze: true,
				freeze_message: __('Creating Purchase Receipt...'),
				callback: function(r) {
					if (!r.exc && r.message) {
						frappe.show_alert({message: __('Purchase Receipt created: ' + r.message), color: 'green'});
						frm.reload_doc();
						frappe.set_route('Form', 'Purchase Receipt', r.message);
					}
				}
			});
		});
	},

	create_purchase_invoices: function(frm) {
		frappe.confirm(__('Are you sure you want to create Purchase Invoices for these shipments?'), function() {
			frappe.call({
				method: "packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.make_purchase_invoices",
				args: { docname: frm.doc.name },
				freeze: true,
				freeze_message: __('Creating Purchase Invoices...'),
				callback: function(r) {
					if (!r.exc && r.message) {
						frappe.show_alert({
							message: __('Successfully created Purchase Invoices: ' + r.message.join(', ')), 
							color: 'green'
						});
						frm.reload_doc();
					}
				}
			});
		});
	}
});