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
					// Fallback to empty template
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
				frappe.call({
					method: "packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.fetch_from_excel",
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
			let d = new frappe.ui.Dialog({
				title: __('Add Remark to Shipment Tracker'),
				fields: [
					{
						label: __('New Remark'),
						fieldname: 'new_remark',
						fieldtype: 'Small Text',
						reqd: 1
					}
				],
				primary_action_label: __('Add'),
				primary_action(values) {
					frappe.call({
						method: 'packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.add_shipment_remark',
						args: {
							docname: frm.doc.name,
							remark: values.new_remark
						},
						callback: function(r) {
							if (!r.exc) {
								frappe.show_alert({message: __('Remark added successfully.'), color: 'green'});
								frm.reload_doc();
								d.hide();
							}
						}
					});
				}
			});
			d.show();
		});
	},
	fetch_pending_items: function(frm) {
		let pos = frm.doc.shipment_pos.map(d => d.purchase_order);
		frappe.call({
			method: "packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.get_outstanding_po_items",
			args: { supplier: frm.doc.supplier, purchase_orders: pos },
			callback: function(r) {
				if (r.message && r.message.length > 0) {
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
						child.line_number = row.line_number;
						child.purchase_order = row.purchase_order;
						child.purchase_order_item = row.purchase_order_item;
					});
					frm.refresh_field('shipment_items');
					frappe.show_alert({message: __('Fetched {0} Pending Items. Validation will be strict on Receipt creation.', [r.message.length]), color: 'blue'});
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
					frappe.db.set_value('Shipment Tracker', frm.doc.name, 'purchase_receipt', r.message)
						.then(() => {
							frm.reload_doc().then(() => {
								frappe.set_route("Form", "Purchase Receipt", r.message);
							});
						});
				}
			}
		});
	},
	create_purchase_invoices: function(frm) {
		frappe.confirm(__('Are you sure you want to create Purchase Invoices?'), () => {
			frappe.call({
				method: "packing_list_reports_fepl.packing.doctype.shipment_tracker.shipment_tracker.create_purchase_invoices",
				args: { docname: frm.doc.name },
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						let msg = __("Purchase Invoice {0} created successfully.", [r.message.join(", ")]);
						frappe.msgprint({
							title: __('Success'),
							indicator: 'green',
							message: msg
						});
						frm.reload_doc();
					} else {
						frappe.msgprint({
							title: __('Notice'),
							indicator: 'orange',
							message: __('No Purchase Invoices were created. Please verify item mappings.')
						});
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
