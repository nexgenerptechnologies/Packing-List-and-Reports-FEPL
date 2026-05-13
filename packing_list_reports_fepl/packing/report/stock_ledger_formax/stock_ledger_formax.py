import frappe
from frappe import _

def execute(filters=None):
	if not filters:
		filters = {}

	columns = get_columns()
	data = get_data(filters)

	return columns, data

def get_columns():
	return [
		{"label": _("Posting Date & Time"), "fieldname": "posting_datetime", "fieldtype": "Datetime", "width": 160},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 120},
		{"label": _("Voucher No"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 160},
		{"label": _("Particulars Name"), "fieldname": "particulars_name", "fieldtype": "Data", "width": 180},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 200},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Link", "options": "Brand", "width": 100},
		{"label": _("SPQ"), "fieldname": "spq", "fieldtype": "Float", "width": 80},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 120},
		{"label": _("In Qty"), "fieldname": "in_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Out Qty"), "fieldname": "out_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Balance Qty"), "fieldname": "balance_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Purchase Rate"), "fieldname": "purchase_rate", "fieldtype": "Currency", "options": "currency", "width": 120},
		{"label": _("Sales Invoice No"), "fieldname": "sales_invoice_no", "fieldtype": "Link", "options": "Sales Invoice", "width": 150},
		{"label": _("Selling Rate"), "fieldname": "selling_rate", "fieldtype": "Currency", "options": "currency", "width": 120},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 80}
	]

def get_data(filters):
	conditions = ""
	if filters.get("item_code"):
		conditions += " AND sle.item_code = %(item_code)s"
	if filters.get("warehouse"):
		conditions += " AND sle.warehouse = %(warehouse)s"
	if filters.get("brand"):
		conditions += " AND i.brand = %(brand)s"
	if filters.get("voucher_type"):
		conditions += " AND sle.voucher_type = %(voucher_type)s"

	query = f"""
		SELECT
			CONCAT(sle.posting_date, ' ', sle.posting_time) AS posting_datetime,
			sle.item_code,
			sle.voucher_type,
			sle.voucher_no,
			sle.voucher_detail_no,
			sle.actual_qty,
			sle.qty_after_transaction AS balance_qty,
			i.item_name,
			i.description,
			i.brand,
			i.custom_standard_packing_qty AS spq,
			i.item_group
		FROM `tabStock Ledger Entry` sle
		JOIN `tabItem` i ON sle.item_code = i.item_code
		WHERE sle.docstatus = 1
		AND sle.posting_date BETWEEN %(from_date)s AND %(to_date)s
		{conditions}
		ORDER BY sle.posting_date ASC, sle.posting_time ASC, sle.name ASC
	"""
	
	raw_data = frappe.db.sql(query, filters, as_dict=1)
	
	enriched_data = []
	for row in raw_data:
		# Quantities
		row['in_qty'] = row['actual_qty'] if row['actual_qty'] > 0 else 0
		row['out_qty'] = abs(row['actual_qty']) if row['actual_qty'] < 0 else 0
		
		# Particulars & Rates & Currency
		v_type = row['voucher_type']
		v_no = row['voucher_no']
		
		particulars = None
		rate = 0
		currency = "INR"
		si_no = None
		
		if v_type in ['Purchase Receipt', 'Purchase Invoice', 'Purchase Order']:
			dt_item = v_type + " Item"
			parent_data = frappe.db.get_value(v_type, v_no, ['supplier', 'currency'], as_dict=1)
			if parent_data:
				particulars = parent_data.supplier
				currency = parent_data.currency
			
			rate = frappe.db.get_value(dt_item, {'parent': v_no, 'item_code': row['item_code']}, 'rate')
			row['purchase_rate'] = rate
			
		elif v_type in ['Sales Invoice', 'Delivery Note']:
			dt_item = v_type + " Item"
			parent_data = frappe.db.get_value(v_type, v_no, ['customer', 'currency'], as_dict=1)
			if parent_data:
				particulars = parent_data.customer
				currency = parent_data.currency
			
			rate = frappe.db.get_value(dt_item, {'parent': v_no, 'item_code': row['item_code']}, 'rate')
			row['selling_rate'] = rate
			
			if v_type == 'Sales Invoice':
				si_no = v_no
			else: # Delivery Note
				si_no = frappe.db.get_value('Sales Invoice Item', {'delivery_note': v_no, 'item_code': row['item_code']}, 'parent')
				
		row['particulars_name'] = particulars
		row['currency'] = currency
		row['sales_invoice_no'] = si_no
		
		enriched_data.append(row)
		
	return enriched_data
