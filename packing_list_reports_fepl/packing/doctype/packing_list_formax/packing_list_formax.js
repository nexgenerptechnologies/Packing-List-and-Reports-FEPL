frappe.ui.form.on('Packing List Formax', {
    setup: function(frm) {
        // Set query for item_code to only show items from the selected Sales Invoice
        frm.set_query('item_code', 'items', function() {
            if (!frm.doc.sales_invoice) {
                return {
                    filters: {
                        'name': ['in', []]
                    }
                };
            }
            return {
                query: "packing_list_reports_fepl.packing.doctype.packing_list_formax.packing_list_formax.get_items_from_si",
                filters: {
                    'sales_invoice': frm.doc.sales_invoice
                }
            };
        });
    },
    refresh: function(frm) {
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Print Stickers'), function() {
                frappe.call({
                    method: 'packing_list_reports_fepl.packing.doctype.packing_list_formax.packing_list_formax.get_print_html',
                    args: { docname: frm.doc.name, print_type: 'Stickers' },
                    callback: function(r) {
                        if (r.message) {
                            var w = window.open();
                            w.document.write(r.message);
                            w.document.close();
                        }
                    }
                });
            }, __('Print'));

            frm.add_custom_button(__('Print Labels'), function() {
                frappe.call({
                    method: 'packing_list_reports_fepl.packing.doctype.packing_list_formax.packing_list_formax.get_print_html',
                    args: { docname: frm.doc.name, print_type: 'Labels' },
                    callback: function(r) {
                        if (r.message) {
                            var w = window.open();
                            w.document.write(r.message);
                            w.document.close();
                        }
                    }
                });
            }, __('Print'));

            frm.add_custom_button(__('Excel: Packing List'), function() {
                var url = frappe.urllib.get_full_url("/api/method/packing_list_reports_fepl.packing.doctype.packing_list_formax.packing_list_formax.download_excel?docname=" + frm.doc.name + "&export_type=Packing List");
                window.open(url, '_blank');
            }, __('Actions'));

            frm.add_custom_button(__('Excel: Stickers Grid'), function() {
                var url = frappe.urllib.get_full_url("/api/method/packing_list_reports_fepl.packing.doctype.packing_list_formax.packing_list_formax.download_excel?docname=" + frm.doc.name + "&export_type=Stickers");
                window.open(url, '_blank');
            }, __('Actions'));

            frm.add_custom_button(__('Excel: Labels Data'), function() {
                var url = frappe.urllib.get_full_url("/api/method/packing_list_reports_fepl.packing.doctype.packing_list_formax.packing_list_formax.download_excel?docname=" + frm.doc.name + "&export_type=Labels");
                window.open(url, '_blank');
            }, __('Actions'));
        }
    },
    sales_invoice: function(frm) {
        if (frm.doc.sales_invoice) {
            frappe.db.get_value('Sales Invoice', frm.doc.sales_invoice, ['customer_name', 'posting_date', 'total_qty'], (r) => {
                if (r) {
                    frm.set_value('customer_name', r.customer_name);
                    frm.set_value('sales_invoice_date', r.posting_date);
                    frm.set_value('total_invoice_qty', r.total_qty);
                }
            });
            
            if (frm.doc.items && frm.doc.items.length > 0) {
                frappe.confirm(__('Changing Sales Invoice will clear the items table. Continue?'), () => {
                    frm.clear_table('items');
                    frm.refresh_field('items');
                    frm.events.calculate_total_quantity(frm);
                });
            }
        } else {
            frm.set_value('customer_name', '');
            frm.set_value('sales_invoice_date', '');
            frm.set_value('total_invoice_qty', 0);
            frm.set_value('total_boxes', 0);
            frm.clear_table('items');
            frm.refresh_field('items');
        }
    },
    calculate_total_quantity: function(frm) {
        // total_boxes equals number of UNIQUE boxes in Packing List Formax
        let unique_boxes = new Set();
        (frm.doc.items || []).forEach(item => {
            if (item.box_number) {
                unique_boxes.add(item.box_number);
            }
        });
        frm.set_value('total_boxes', unique_boxes.size);
        
        // Ensure total_invoice_qty is synced if missing
        if (!frm.doc.total_invoice_qty && frm.doc.sales_invoice) {
            frappe.db.get_value('Sales Invoice', frm.doc.sales_invoice, 'total_qty', (r) => {
                if (r) frm.set_value('total_invoice_qty', r.total_qty);
            });
        }
    }
});

frappe.ui.form.on('Packing List Formax Item', {
    box_number: function(frm, cdt, cdn) {
        frm.events.calculate_total_quantity(frm);
    },
    items_remove: function(frm, cdt, cdn) {
        frm.events.calculate_total_quantity(frm);
    },
    items_add: function(frm, cdt, cdn) {
        frm.events.calculate_total_quantity(frm);
    },
    item_code: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.item_code && frm.doc.sales_invoice) {
            frappe.call({
                method: "packing_list_reports_fepl.packing.doctype.packing_list_formax.packing_list_formax.get_si_item_details",
                args: {
                    sales_invoice: frm.doc.sales_invoice,
                    item_code: row.item_code
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'item_name', r.message.item_name);
                        frappe.model.set_value(cdt, cdn, 'description', r.message.description);
                        frappe.model.set_value(cdt, cdn, 'quantity', r.message.qty);
                        frappe.model.set_value(cdt, cdn, 'custom_cpn', r.message.custom_cpn);
                    }
                }
            });
        }
    }
});
