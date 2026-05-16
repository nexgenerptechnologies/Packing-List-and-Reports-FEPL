frappe.ui.form.on('Item Allocation Sheet', {
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
	}
});
