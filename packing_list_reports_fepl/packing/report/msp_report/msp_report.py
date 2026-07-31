import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
	if not filters: filters = {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 200},
		{"label": _("MSP"), "fieldname": "msp", "fieldtype": "Currency", "width": 100},
		{"label": _("Sale Price"), "fieldname": "sale_price", "fieldtype": "Currency", "width": 100},
		{"label": _("Net loss"), "fieldname": "net_loss", "fieldtype": "Currency", "width": 100},
		{"label": _("% loss"), "fieldname": "loss_percent", "fieldtype": "Percent", "width": 80},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 150},
		{"label": _("Sales Invoice No."), "fieldname": "sales_invoice_no", "fieldtype": "Link", "options": "Sales Invoice", "width": 140},
		{"label": _("Sales Invoice Date"), "fieldname": "sales_invoice_date", "fieldtype": "Date", "width": 100},
		{"label": _("Sales Partner"), "fieldname": "sales_partner", "fieldtype": "Link", "options": "Sales Partner", "width": 120}
	]

def get_data(filters):
	conditions = ""
	if filters.get("from_date"): conditions += " AND si.posting_date >= %(from_date)s"
	if filters.get("to_date"): conditions += " AND si.posting_date <= %(to_date)s"
	if filters.get("customer"): conditions += " AND si.customer = %(customer)s"
	if filters.get("item_code"): conditions += " AND sii.item_code = %(item_code)s"
	
	# Check if custom_msp actually exists to prevent crash
	if not frappe.db.has_column("Item", "custom_msp"):
		return []

	sql = f"""
		SELECT
			sii.item_code AS item_code,
			sii.item_name AS item_name,
			sii.description AS description,
			i.custom_msp AS msp,
			sii.base_rate AS sale_price,
			(i.custom_msp - sii.base_rate) AS net_loss,
			si.customer_name AS customer_name,
			si.name AS sales_invoice_no,
			si.posting_date AS sales_invoice_date,
			si.sales_partner AS sales_partner
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent AND si.docstatus = 1 AND si.is_return = 0
		INNER JOIN `tabItem` i ON i.name = sii.item_code
		WHERE i.custom_msp > 0 
		AND sii.base_rate < i.custom_msp
		{conditions}
		ORDER BY si.posting_date DESC, si.name DESC
	"""
	
	raw_data = frappe.db.sql(sql, filters, as_dict=True)
	
	for d in raw_data:
		msp = flt(d.msp)
		net_loss = flt(d.net_loss)
		d["loss_percent"] = (net_loss / msp) * 100 if msp else 0.0
		
	return raw_data