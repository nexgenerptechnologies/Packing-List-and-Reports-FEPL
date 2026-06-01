import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
	if not frappe.db.get_single_value('Packing List Settings', 'enable_stock_ledger_formax'):
		frappe.throw(_('Stock Ledger Formax is disabled in Packing List Settings.'))
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
	if not raw_data:
		return []

	# Group parent docnames by DocType for bulk retrieval
	purchase_types = ['Purchase Receipt', 'Purchase Invoice', 'Purchase Order']
	sales_types = ['Sales Invoice', 'Delivery Note']
	vouchers_by_type = {}
	
	for row in raw_data:
		v_type = row['voucher_type']
		v_no = row['voucher_no']
		if v_type and v_no:
			vouchers_by_type.setdefault(v_type, set()).add(v_no)

	# 1. Bulk fetch particulars and currency
	parent_info = {} # key: (voucher_type, voucher_no) -> {particulars, currency}
	
	for v_type, v_nos in vouchers_by_type.items():
		v_nos_list = list(v_nos)
		if v_type in purchase_types:
			p_data = frappe.get_all(v_type,
				filters={"name": ["in", v_nos_list]},
				fields=["name", "supplier", "currency"])
			for p in p_data:
				parent_info[(v_type, p.name)] = {
					"particulars": p.supplier,
					"currency": p.currency
				}
		elif v_type in sales_types:
			p_data = frappe.get_all(v_type,
				filters={"name": ["in", v_nos_list]},
				fields=["name", "customer", "currency"])
			for p in p_data:
				parent_info[(v_type, p.name)] = {
					"particulars": p.customer,
					"currency": p.currency
				}

	# 2. Bulk fetch rates from child tables
	rates_info = {} # key: (dt_item, parent, item_code) -> rate
	for v_type, v_nos in vouchers_by_type.items():
		if v_type in (purchase_types + sales_types):
			dt_item = v_type + " Item"
			child_data = frappe.get_all(dt_item,
				filters={"parent": ["in", list(v_nos)]},
				fields=["parent", "item_code", "rate"])
			for c in child_data:
				rates_info[(dt_item, c.parent, c.item_code)] = c.rate

	# 3. Bulk fetch Delivery Note linked Sales Invoices
	dn_invoices = {} # key: (dn_no, item_code) -> parent sales invoice
	if 'Delivery Note' in vouchers_by_type:
		si_items = frappe.get_all('Sales Invoice Item',
			filters={"delivery_note": ["in", list(vouchers_by_type['Delivery Note'])]},
			fields=["delivery_note", "item_code", "parent"])
		for s in si_items:
			dn_invoices[(s.delivery_note, s.item_code)] = s.parent

	# 4. Map the fetched data back to each row
	enriched_data = []
	for row in raw_data:
		row['in_qty'] = row['actual_qty'] if row['actual_qty'] > 0 else 0
		row['out_qty'] = abs(row['actual_qty']) if row['actual_qty'] < 0 else 0
		
		v_type = row['voucher_type']
		v_no = row['voucher_no']
		
		particulars = None
		rate = 0
		currency = "INR"
		si_no = None
		
		p_key = (v_type, v_no)
		if p_key in parent_info:
			particulars = parent_info[p_key]["particulars"]
			currency = parent_info[p_key]["currency"]
			
		if v_type in purchase_types:
			dt_item = v_type + " Item"
			rate = rates_info.get((dt_item, v_no, row['item_code']), 0)
			row['purchase_rate'] = rate
			row['selling_rate'] = 0
			
		elif v_type in sales_types:
			dt_item = v_type + " Item"
			rate = rates_info.get((dt_item, v_no, row['item_code']), 0)
			row['selling_rate'] = rate
			row['purchase_rate'] = 0
			
			if v_type == 'Sales Invoice':
				si_no = v_no
			else:
				si_no = dn_invoices.get((v_no, row['item_code']))
				
		row['particulars_name'] = particulars
		row['currency'] = currency
		row['sales_invoice_no'] = si_no
		
		enriched_data.append(row)
		
	return enriched_data
