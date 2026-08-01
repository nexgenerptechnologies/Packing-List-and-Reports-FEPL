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
			"fieldtype": "Link",
			"options": "DocType",
			"get_query": function() {
				return {
					filters: {
						"name": ["in", ["Purchase Invoice", "Journal Entry", "Payment Entry"]]
					}
				}
			}
		},
		{
			"fieldname": "party_type",
			"label": __("Party Type"),
			"fieldtype": "Link",
			"options": "DocType",
			"default": "Supplier"
		},
		{
			"fieldname": "party",
			"label": __("Party"),
			"fieldtype": "Dynamic Link",
			"options": "party_type"
		}
	],
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === 'particulars' && data.particulars) {
			// Allow multi-line display for Party + Voucher
			value = <div style="white-space: pre-wrap; font-size: 12px; line-height: 1.4;"> + value + </div>;
		}
		return value;
	}
};