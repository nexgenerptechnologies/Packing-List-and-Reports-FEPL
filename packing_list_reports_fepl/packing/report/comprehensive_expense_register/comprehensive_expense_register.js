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
			"fieldname": "party_type",
			"label": __("Party Type"),
			"fieldtype": "Link",
			"options": "DocType",
			"default": "Supplier",
			"get_query": function() {
				return {
					filters: {
						"name": ["in", ["Supplier", "Customer", "Employee"]]
					}
				}
			}
		},
		{
			"fieldname": "party",
			"label": __("Party"),
			"fieldtype": "Dynamic Link",
			"options": "party_type"
		},
		{
			"fieldname": "account",
			"label": __("Account"),
			"fieldtype": "Link",
			"options": "Account",
			"get_query": function() {
				var company = frappe.query_report.get_filter_value('company');
				return {
					filters: {
						"company": company,
						"is_group": 0
					}
				}
			}
		}
	],
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === 'particulars' && data.particulars) {
			value = '<div style="white-space: pre-wrap; font-size: 12px; line-height: 1.4;">' + value + '</div>';
		}
		return value;
	}
};