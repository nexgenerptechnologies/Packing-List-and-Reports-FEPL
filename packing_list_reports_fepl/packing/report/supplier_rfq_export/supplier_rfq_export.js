frappe.query_reports["Supplier RFQ Export"] = {
	"filters": [
		{
			"fieldname": "quotation",
			"label": __("Quotation Number"),
			"fieldtype": "Link",
			"options": "Quotation",
			"reqd": 1
		}
	]
};
