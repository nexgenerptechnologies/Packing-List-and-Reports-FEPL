frappe.ui.form.on('Item Allocation Sheet', {
	item_code: function(frm) {
		if (frm.doc.item_code) {
			frappe.db.get_value('Item', frm.doc.item_code, 'item_name', (r) => {
				if (r) frm.set_value('item_name', r.item_name);
			});
			frm.trigger('update_stock');
		}
	},
	warehouse: function(frm) {
		frm.trigger('update_stock');
	},
	refresh: function(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.excel_file) {
			frm.add_custom_button(__('Process Excel Planning'), function() {
				frm.events.process_excel(frm);
			});
		}
	},
	process_excel: function(frm) {
		frappe.call({
			method: "packing_list_reports_fepl.packing.doctype.item_allocation_sheet.item_allocation_sheet.process_excel_upload",
			args: {
				docname: frm.doc.name
			},
			callback: function(r) {
				if (r.message) {
					frm.reload_doc();
					frappe.show_alert({message: __('Excel Processed Successfully'), color: 'green'});
				}
			}
		});
	},
	update_stock: function(frm) {
		if (frm.doc.item_code && frm.doc.warehouse) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Bin",
					filters: { item_code: frm.doc.item_code, warehouse: frm.doc.warehouse },
					fieldname: "actual_qty"
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('total_available_stock', r.message.actual_qty);
					} else {
						frm.set_value('total_available_stock', 0);
					}
				}
			});
		}
	}
});
