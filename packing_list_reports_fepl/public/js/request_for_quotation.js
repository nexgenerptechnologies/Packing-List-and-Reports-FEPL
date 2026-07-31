frappe.ui.form.on('Request for Quotation', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Upload Supplier Excel'), function() {
                new frappe.ui.FileUploader({
                    doctype: frm.doc.doctype,
                    docname: frm.doc.name,
                    on_success: (file_doc) => {
                        frappe.call({
                            method: "packing_list_reports_fepl.packing.api.upload_supplier_excel",
                            args: {
                                rfq_name: frm.doc.name,
                                file_url: file_doc.file_url
                            },
                            callback: function(r) {
                                if (!r.exc) {
                                    frappe.msgprint(__('Successfully imported supplier pricing from Excel!'));
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                });
            }, __('Get Excel'));
            frm.add_custom_button(__('Download Excel Template'), function() {
                let url = "/api/method/packing_list_reports_fepl.packing.api.download_supplier_rfq?rfq_name=" + encodeURIComponent(frm.doc.name);
                window.open(url, "_self");
            }, __('Get Excel'));
        }
    }
});