frappe.ui.form.on('Request for Quotation', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Supplier RFQ Export'), function() {
                let route = ['query-report', 'Supplier RFQ Export', { 'quotation': frm.doc.name }];
                frappe.set_route(route);
            }, __('Get Excel'));
        }
    }
});