frappe.ui.form.on('Request for Quotation', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Download Excel Template'), function() {
                let url = "/api/method/packing_list_reports_fepl.packing.api.download_supplier_rfq?rfq_name=" + encodeURIComponent(frm.doc.name);
                window.open(url, "_self");
            }, __('Get Excel'));
        }
    }
});