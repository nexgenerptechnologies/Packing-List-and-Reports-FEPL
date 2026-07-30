app_name = "packing_list_reports_fepl"
app_title = "Packing List Reports FEPL"
app_publisher = "NexGen ERP Technologies"
app_description = "Packing List and Reports for FEPL"
app_email = "admin@example.com"
app_license = "mit"

doctype_js = {
    "Sales Invoice": "public/js/sales_invoice.js",
    "Delivery Note": "public/js/delivery_note.js",
    "Purchase Receipt": "public/js/purchase_receipt.js",
    "Request for Quotation": "public/js/request_for_quotation.js"
}

doc_events = {
	"Purchase Order": {
		"validate": "packing_list_reports_fepl.packing.doctype.packing_list_settings.packing_list_settings.update_po_line_numbers"
	}
}

fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "Packing"]]}
]
