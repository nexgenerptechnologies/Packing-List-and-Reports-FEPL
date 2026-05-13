frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Create Packing List'), function() {
                frappe.new_doc('Packing List Formax', {
                    sales_invoice: frm.doc.name
                });
            }, __('Create'));
        }
    }
});
