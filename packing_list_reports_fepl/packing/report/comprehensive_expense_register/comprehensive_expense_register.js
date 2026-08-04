frappe.query_reports["Comprehensive Expense Register"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname": "voucher_type",
			"label": __("Voucher Type"),
			"fieldtype": "Select",
			"options": "\nPurchase Invoice\nJournal Entry\nPayment Entry"
		},
		{
			"fieldname": "party",
			"label": __("Supplier / Party"),
			"fieldtype": "Link",
			"options": "Supplier"
		},
		{
			"fieldname": "account",
			"label": __("Account"),
			"fieldtype": "MultiSelectList",
			"options": "Account",
			"get_data": function(txt) {
				return frappe.db.get_link_options("Account", txt, {
					company: frappe.query_report.get_filter_value("company")
				});
			}
		}
	]
};