frappe.query_reports["Pending SO Report Formax"] = {
	"filters": [
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
			"fieldname": "customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname": "item_code",
			"label": __("Item Code"),
			"fieldtype": "Link",
			"options": "Item"
		},
		{
			"fieldname": "brand",
			"label": __("Brand"),
			"fieldtype": "Link",
			"options": "Brand"
		},
		{
			"fieldname": "sales_partner",
			"label": __("Sales Partner"),
			"fieldtype": "Link",
			"options": "Sales Partner"
		}
	],
	onload: function(report) {
		frappe.db.get_single_value('Packing List Settings', 'enable_pending_so_report_formax').then(val => {
			if (val === 0 || val === '0') {
				frappe.msgprint({
					title: __('Report Disabled'),
					indicator: 'red',
					message: __('Pending SO Report Formax is disabled. Click <a href=/app/packing-list-settings>here</a> to go to Settings and enable it.')
				});
			}
		});
	}
};
