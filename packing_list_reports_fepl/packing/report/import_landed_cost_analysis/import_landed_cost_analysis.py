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
		{"label": _("Purchase Invoice Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Purchase Invoice No."), "fieldname": "purchase_invoice", "fieldtype": "Link", "options": "Purchase Invoice", "width": 140},
		{"label": _("Supplier Name"), "fieldname": "supplier", "fieldtype": "Data", "width": 150},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 200},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 100},
		{"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 100},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Exchange Rate"), "fieldname": "conversion_rate", "fieldtype": "Float", "width": 100},
		{"label": _("Price in INR"), "fieldname": "price_in_inr", "fieldtype": "Currency", "width": 120},
		{"label": _("BE Number"), "fieldname": "be_number", "fieldtype": "Data", "width": 120},
		{"label": _("BE Date"), "fieldname": "be_date", "fieldtype": "Date", "width": 100},
		{"label": _("BCD Percent"), "fieldname": "bcd_percent", "fieldtype": "Currency", "width": 100},
		{"label": _("Freight"), "fieldname": "freight", "fieldtype": "Currency", "width": 100},
		{"label": _("CHA Charges"), "fieldname": "cha_charges", "fieldtype": "Currency", "width": 100},
		{"label": _("Landing Cost"), "fieldname": "landing_cost", "fieldtype": "Currency", "width": 120},
		{"label": _("Stock Qty"), "fieldname": "stock_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 150},
		{"label": _("Sale Price"), "fieldname": "sale_price", "fieldtype": "Currency", "width": 100},
		{"label": _("Sales Invoice No."), "fieldname": "sales_invoice_no", "fieldtype": "Link", "options": "Sales Invoice", "width": 140},
		{"label": _("Sales Invoice Date"), "fieldname": "sales_invoice_date", "fieldtype": "Date", "width": 100}
	]

def get_data(filters):
	conditions = ""
	if filters.get("from_date"): conditions += " AND pi.posting_date >= %(from_date)s"
	if filters.get("to_date"): conditions += " AND pi.posting_date <= %(to_date)s"
	if filters.get("supplier"): conditions += " AND pi.supplier = %(supplier)s"
	if filters.get("item_code"): conditions += " AND pii.item_code = %(item_code)s"

	has_boe = frappe.db.exists("DocType", "Bill of Entry")
	boe_join = ""
	if has_boe:
		boe_join = """
			LEFT JOIN `tabBill of Entry Item` boei ON boei.purchase_invoice = pi.name AND boei.item = pii.item_code
			LEFT JOIN `tabBill of Entry` boe ON boe.name = boei.parent AND boe.docstatus = 1
		"""

	sql = f"""
		SELECT
			pi.posting_date AS posting_date,
			pi.name AS purchase_invoice,
			pi.supplier AS supplier,
			pii.item_code AS item_code,
			pii.item_name AS item_name,
			pii.description AS description,
			pii.qty AS qty,
			pii.rate AS rate,
			pii.amount AS amount,
			pi.conversion_rate AS conversion_rate,
			(pii.rate * pi.conversion_rate) AS price_in_inr,
			
			{"boe.bill_of_entry_no" if has_boe else "''"} AS be_number,
			{"boe.bill_of_entry_date" if has_boe else "NULL"} AS be_date,
			{"boei.customs_and_additional_charges" if has_boe else "0.0"} AS total_bcd,
			
			(
				SELECT SUM(lci.applicable_charges)
				FROM `tabLanded Cost Item` lci
				INNER JOIN `tabLanded Cost Voucher` lcv ON lcv.name = lci.parent AND lcv.docstatus = 1
				INNER JOIN `tabLanded Cost Purchase Receipt` lcpr ON lcpr.parent = lcv.name
				WHERE (lcpr.receipt_document = pi.name OR lcpr.receipt_document = pii.purchase_receipt) AND lci.item_code = pii.item_code
			) AS total_lcv_charges,
			
			(
				SELECT SUM(actual_qty) FROM `tabBin` WHERE item_code = pii.item_code
			) AS stock_qty,
			
			(
				SELECT sii.parent
				FROM `tabSales Invoice Item` sii
				INNER JOIN `tabSales Invoice` si ON si.name = sii.parent AND si.docstatus = 1
				WHERE sii.item_code = pii.item_code
				ORDER BY si.posting_date DESC, si.name DESC
				LIMIT 1
			) AS sales_invoice_no,
			(
				SELECT si.posting_date
				FROM `tabSales Invoice Item` sii
				INNER JOIN `tabSales Invoice` si ON si.name = sii.parent AND si.docstatus = 1
				WHERE sii.item_code = pii.item_code
				ORDER BY si.posting_date DESC, si.name DESC
				LIMIT 1
			) AS sales_invoice_date,
			(
				SELECT si.customer_name
				FROM `tabSales Invoice Item` sii
				INNER JOIN `tabSales Invoice` si ON si.name = sii.parent AND si.docstatus = 1
				WHERE sii.item_code = pii.item_code
				ORDER BY si.posting_date DESC, si.name DESC
				LIMIT 1
			) AS customer_name,
			(
				SELECT sii.rate
				FROM `tabSales Invoice Item` sii
				INNER JOIN `tabSales Invoice` si ON si.name = sii.parent AND si.docstatus = 1
				WHERE sii.item_code = pii.item_code
				ORDER BY si.posting_date DESC, si.name DESC
				LIMIT 1
			) AS sale_price

		FROM `tabPurchase Invoice Item` pii
		INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent AND pi.docstatus = 1
		{boe_join}
		WHERE 1=1 {conditions}
		ORDER BY pi.posting_date DESC, pi.name DESC
	"""
	
	raw_data = frappe.db.sql(sql, filters, as_dict=True)
	
	for d in raw_data:
		qty = flt(d.qty) or 1.0
		price_in_inr = flt(d.price_in_inr)
		
		# Convert total charges to per-unit
		d["bcd_percent"] = flt(d.total_bcd) / qty
		total_lcv = flt(d.total_lcv_charges) / qty
		
		# Since ERPNext lumps all charges into applicable_charges, we dump it into Freight.
		d["freight"] = total_lcv
		d["cha_charges"] = 0.0
		
		d["landing_cost"] = price_in_inr + d["bcd_percent"] + d["freight"] + d["cha_charges"]
		
	return raw_data