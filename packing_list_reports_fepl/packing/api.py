import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.xlsxutils import make_xlsx

@frappe.whitelist(allow_guest=False)
def download_supplier_rfq(rfq_name):
	if not frappe.has_permission("Request for Quotation", "read"):
		frappe.throw(_("Not permitted"))

	columns = [
		{"label": "RFQ ID", "fieldname": "rfq_id"},
		{"label": "RFQ Date", "fieldname": "rfq_date"},
		{"label": "Customer Name", "fieldname": "customer_name"},
		{"label": "Project", "fieldname": "project"},
		{"label": "SOP Date", "fieldname": "sop_date"},
		{"label": "Item Code", "fieldname": "item_code"},
		{"label": "Item Name", "fieldname": "item_name"},
		{"label": "Description", "fieldname": "description"},
		{"label": "Brand", "fieldname": "brand"},
		{"label": "Monthly Qty", "fieldname": "monthly_qty"},
		{"label": "Customer Description", "fieldname": "customer_description"},
		{"label": "Sales Partner", "fieldname": "sales_partner"},
		{"label": "Stock", "fieldname": "stock_qty"},
		{"label": "Reserved Stock", "fieldname": "reserved_stock"},
		{"label": "Supplier MPN", "fieldname": "supplier_mpn"},
		{"label": "Supplier Description", "fieldname": "supplier_description"},
		{"label": "MAKE", "fieldname": "make"},
		{"label": "SPQ", "fieldname": "spq"},
		{"label": "Lead Time", "fieldname": "lead_time"},
		{"label": "Price Per 1000", "fieldname": "price_per_1000"},
		{"label": "Quote date", "fieldname": "quote_date"},
		{"label": "Remarks", "fieldname": "remarks"}
	]

	q = frappe.get_doc("Request for Quotation", rfq_name)
	
	item_codes = [d.item_code for d in q.items if d.item_code]
	stock_qty_map = {}
	reserved_stock_map = {}
	
	if item_codes:
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

	data = [[c["label"] for c in columns]]
	
	for item in q.items:
		brand = item.get("brand") or frappe.db.get_value("Item", item.item_code, "brand") or ""
		sop = item.get("custom_sop_date") or q.get("custom_sop_date") or ""
		mq = item.get("custom_monthly_qty") or item.qty or 0.0
		cd = item.get("custom_customer_description") or ""
		
		row_dict = {
			"rfq_id": q.name,
			"rfq_date": str(q.transaction_date) if q.transaction_date else "",
			"customer_name": q.get("custom_customer_name") or "",
			"project": q.get("custom_project") or "",
			"sop_date": str(sop) if sop else "",
			"item_code": item.item_code,
			"item_name": item.item_name or "",
			"description": item.description or "",
			"brand": brand,
			"monthly_qty": mq,
			"customer_description": cd,
			"sales_partner": q.get("custom_sales_partner") or "",
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
		
		row_list = [row_dict.get(c["fieldname"]) for c in columns]
		data.append(row_list)

	xlsx_file = make_xlsx(data, "Supplier RFQ")
	
	frappe.response["filename"] = f"{rfq_name}_Supplier_RFQ.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "binary"