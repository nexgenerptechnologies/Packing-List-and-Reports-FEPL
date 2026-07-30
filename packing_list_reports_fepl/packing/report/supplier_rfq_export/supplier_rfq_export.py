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
		{"label": _("RFQ ID"), "fieldname": "rfq_id", "fieldtype": "Link", "options": "Request for Quotation", "width": 120},
		{"label": _("RFQ Date"), "fieldname": "rfq_date", "fieldtype": "Date", "width": 100},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 150},
		{"label": _("Project"), "fieldname": "project", "fieldtype": "Data", "width": 120},
		{"label": _("SOP Date"), "fieldname": "sop_date", "fieldtype": "Date", "width": 100},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 200},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Link", "options": "Brand", "width": 100},
		{"label": _("Monthly Qty"), "fieldname": "monthly_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Customer Description"), "fieldname": "customer_description", "fieldtype": "Data", "width": 150},
		{"label": _("Sales Partner"), "fieldname": "sales_partner", "fieldtype": "Link", "options": "Sales Partner", "width": 120},
		{"label": _("Stock"), "fieldname": "stock_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Reserved Stock"), "fieldname": "reserved_stock", "fieldtype": "Float", "width": 120},
		{"label": _("Supplier MPN"), "fieldname": "supplier_mpn", "fieldtype": "Data", "width": 120},
		{"label": _("Supplier Description"), "fieldname": "supplier_description", "fieldtype": "Data", "width": 150},
		{"label": _("MAKE"), "fieldname": "make", "fieldtype": "Data", "width": 100},
		{"label": _("SPQ"), "fieldname": "spq", "fieldtype": "Data", "width": 100},
		{"label": _("Lead Time"), "fieldname": "lead_time", "fieldtype": "Data", "width": 100},
		{"label": _("Price Per 1000"), "fieldname": "price_per_1000", "fieldtype": "Currency", "width": 120},
		{"label": _("Quote date"), "fieldname": "quote_date", "fieldtype": "Date", "width": 100},
		{"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 150}
	]

def get_data(filters):
	if not filters.get("quotation"):
		return []

	q = frappe.get_doc("Request for Quotation", filters.get("quotation"))
	
	item_codes = [d.item_code for d in q.items if d.item_code]
	if not item_codes:
		return []

	bin_data = frappe.db.sql("""
		SELECT item_code, SUM(actual_qty) AS stock_qty
		FROM `tabBin`
		WHERE item_code IN %s
		GROUP BY item_code
	""", (tuple(item_codes),), as_dict=1)
	stock_qty_map = {b.item_code: flt(b.stock_qty) for b in bin_data}

	reserved_data = frappe.db.sql("""
		SELECT item_code, SUM(reserved_qty - IFNULL(delivered_qty, 0)) AS reserved_qty
		FROM `tabStock Reservation Entry`
		WHERE docstatus = 1 AND item_code IN %s
		GROUP BY item_code
	""", (tuple(item_codes),), as_dict=1)
	reserved_stock_map = {r.item_code: flt(r.reserved_qty) for r in reserved_data}

	data = []
	for item in q.items:
		brand = item.get("brand") or frappe.db.get_value("Item", item.item_code, "brand")
		sop = item.get("custom_sop_date") or q.get("custom_sop_date")
		mq = item.get("custom_monthly_qty") or item.qty
		cd = item.get("custom_customer_description")
		
		row = {
			"rfq_id": q.name,
			"rfq_date": q.transaction_date,
			"customer_name": q.get("custom_customer_name"),
			"project": q.get("custom_project"),
			"sop_date": sop,
			"item_code": item.item_code,
			"item_name": item.item_name,
			"description": item.description,
			"brand": brand,
			"monthly_qty": mq,
			"customer_description": cd,
			"sales_partner": q.get("custom_sales_partner"),
			"stock_qty": stock_qty_map.get(item.item_code, 0.0),
			"reserved_stock": reserved_stock_map.get(item.item_code, 0.0),
			"supplier_mpn": "",
			"supplier_description": "",
			"make": "",
			"spq": "",
			"lead_time": "",
			"price_per_1000": "",
			"quote_date": "",
			"remarks": ""
		}
		data.append(row)
	return data