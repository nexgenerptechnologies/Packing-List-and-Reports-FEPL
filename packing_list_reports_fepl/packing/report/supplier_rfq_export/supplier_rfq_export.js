frappe.query_reports["Supplier RFQ Export"] = {
	"filters": [
		{
			"fieldname": "quotation",
			"label": __("RFQ Number"),
			"fieldtype": "Link",
			"options": "Request for Quotation",
			"reqd": 1
		}
	],
	"onload": function(report) {
		report.page.add_inner_button(__("Download Excel"), function() {
			report.export_report("Excel");
		});
	}
};