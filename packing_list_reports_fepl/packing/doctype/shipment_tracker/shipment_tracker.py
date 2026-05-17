import frappe
from frappe.model.document import Document
from frappe import _

class ShipmentTracker(Document):
	def before_submit(self):
		if not self.shipment_items or len(self.shipment_items) == 0:
			frappe.throw(_("Please fetch or add items to the shipment before submitting."))
			
		for item in self.shipment_items:
			if item.qty > 0:
				if not item.purchase_order_item:
					if not item.line_number:
						frappe.throw(_("Row {0}: Item {1} is missing both Purchase Order Item and Line Number. Cannot auto-link.").format(item.idx, item.item_code))
					
					# Auto-link based on custom_line_number and supplier
					po_items = frappe.db.sql("""
						SELECT poi.name, poi.parent 
						FROM `tabPurchase Order Item` poi
						JOIN `tabPurchase Order` po ON poi.parent = po.name
						WHERE poi.custom_line_number = %s AND poi.item_code = %s AND po.supplier = %s AND po.docstatus = 1
					""", (item.line_number, item.item_code, self.supplier), as_dict=1)
					
					if po_items:
						item.purchase_order = po_items[0].parent
						item.purchase_order_item = po_items[0].name
					else:
						frappe.throw(_("Row {0}: Could not find a matching Purchase Order for Line Number '{1}' and Item '{2}'.").format(item.idx, item.line_number, item.item_code))
				
				po_item = frappe.get_doc("Purchase Order Item", item.purchase_order_item)
				po_line_number = po_item.get("custom_line_number") or str(po_item.idx)
				
				discrepancies = []
				if item.item_code != po_item.item_code: discrepancies.append(_("Item Code mismatch (Expected: '{0}', Got: '{1}')").format(po_item.item_code, item.item_code))
				if item.item_name and po_item.item_name and str(item.item_name).strip() != str(po_item.item_name).strip(): discrepancies.append(_("Item Name mismatch (Expected: '{0}', Got: '{1}')").format(po_item.item_name, item.item_name))
				if item.description and po_item.description and str(item.description).strip() != str(po_item.description).strip(): discrepancies.append(_("Description mismatch (Expected: '{0}', Got: '{1}')").format(po_item.description, item.description))
				if item.qty > (po_item.qty - po_item.received_qty): discrepancies.append(_("Quantity exceeds pending amount (Pending: {0}, Got: {1})").format(po_item.qty - po_item.received_qty, item.qty))
				if abs(float(item.rate) - float(po_item.rate)) > 0.01: discrepancies.append(_("Rate mismatch (Expected: {0}, Got: {1})").format(po_item.rate, item.rate))
				
				if item.line_number and str(item.line_number).strip() != str(po_line_number).strip():
					discrepancies.append(_("Line Number mismatch (Expected: '{0}', Got: '{1}')").format(po_line_number, item.line_number))
				
				if discrepancies:
					frappe.throw(_("Row {0}: Validation Failed for Item {1}.\n{2}").format(item.idx, item.item_code, "\n".join(discrepancies)))


@frappe.whitelist()
def get_outstanding_po_items(supplier, purchase_orders):
	if isinstance(purchase_orders, str):
		import json
		purchase_orders = json.loads(purchase_orders)
		
	if not purchase_orders:
		return []

	# Use custom_line_number if exists, otherwise fallback to idx (sequence number)
	return frappe.db.sql("""
		SELECT 
			poi.item_code, poi.item_name, poi.description, 
			(poi.qty - poi.received_qty) as qty, poi.rate, 
			poi.custom_line_number as line_number,
			poi.parent as purchase_order, poi.name as purchase_order_item,
			po.currency, po.conversion_rate
		FROM `tabPurchase Order Item` poi
		JOIN `tabPurchase Order` po ON poi.parent = po.name
		WHERE po.supplier = %s AND po.name IN ({0}) AND po.docstatus = 1 AND poi.qty > poi.received_qty
		ORDER BY po.name, poi.idx ASC
	""".format(", ".join(["'{0}'".format(d) for d in purchase_orders])), (supplier), as_dict=1)

@frappe.whitelist()
def make_purchase_receipt(docname):
	source_doc = frappe.get_doc("Shipment Tracker", docname)
	
	if source_doc.purchase_receipt:
		frappe.throw(_("Purchase Receipt already created for this shipment: {0}").format(source_doc.purchase_receipt))
	
	target_doc = frappe.new_doc("Purchase Receipt")
	target_doc.supplier = source_doc.supplier
	
	company, currency, conversion_rate = None, None, 1.0
	if source_doc.shipment_items:
		po_data = frappe.db.get_value("Purchase Order", source_doc.shipment_items[0].purchase_order, ["company", "currency", "conversion_rate"], as_dict=1)
		if po_data:
			company, currency, conversion_rate = po_data.company, po_data.currency, po_data.conversion_rate
					
	target_doc.company = company or frappe.defaults.get_global_default("company")
	target_doc.posting_date = frappe.utils.nowdate()
	target_doc.currency = currency
	target_doc.conversion_rate = conversion_rate
	
	for item in source_doc.shipment_items:
		if item.qty > 0:
			po_item = frappe.get_doc("Purchase Order Item", item.purchase_order_item)

			pr_item = target_doc.append("items", {})
			pr_item.item_code = item.item_code
			pr_item.qty = item.qty
			pr_item.rate = item.rate
			pr_item.purchase_order = item.purchase_order
			pr_item.purchase_order_item = item.purchase_order_item
			pr_item.uom = po_item.uom
			pr_item.stock_uom = po_item.stock_uom
			pr_item.conversion_factor = po_item.conversion_factor
					
	target_doc.insert()
	return target_doc.name

@frappe.whitelist()
def create_purchase_invoices(docname):
	source_doc = frappe.get_doc("Shipment Tracker", docname)
	if not source_doc.purchase_receipt:
		frappe.throw(_("Please link a Purchase Receipt first."))
		
	invoice_groups = {}
	for item in source_doc.shipment_items:
		inv_no = item.supplier_invoice
		if inv_no:
			if inv_no not in invoice_groups: invoice_groups[inv_no] = []
			invoice_groups[inv_no].append(item)
		
	created_invoices = []
	from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
	
	for inv_no, items in invoice_groups.items():
		pi = make_purchase_invoice(source_doc.purchase_receipt)
		pi.bill_no = inv_no
		pi.bill_date = items[0].bill_date or frappe.utils.nowdate()
		
		group_po_items = [it.purchase_order_item for it in items]
		new_items = [pi_item for pi_item in pi.get("items") if pi_item.po_detail in group_po_items]
		pi.set("items", new_items)
		
		if pi.get("items"):
			pi.insert()
			created_invoices.append(pi.name)
			for row in source_doc.shipment_invoices:
				if row.bill_no == inv_no:
					row.db_set("purchase_invoice", pi.name)
					break
					
	return created_invoices

@frappe.whitelist()
def has_purchase_invoices(purchase_receipt):
	active_invoices = frappe.db.sql("""
		SELECT 1 
		FROM `tabPurchase Invoice Item` pii
		JOIN `tabPurchase Invoice` pi ON pii.parent = pi.name
		WHERE pii.purchase_receipt = %s AND pi.docstatus < 2
		LIMIT 1
	""", (purchase_receipt,))
	return len(active_invoices) > 0

@frappe.whitelist()
def fetch_from_excel(docname):
	doc = frappe.get_doc("Shipment Tracker", docname)
	if not doc.excel_file:
		frappe.throw(_("Please attach an Excel file first."))
		
	import openpyxl
	from frappe.utils import flt, getdate
	import datetime
	
	try:
		file_doc = frappe.get_doc("File", {"file_url": doc.excel_file})
		wb = openpyxl.load_workbook(file_doc.get_full_path(), data_only=True)
		sheet = wb.active
		
		header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True))
		col_map = {}
		expected = {
			"item_code": ["Item Code", "item code"],
			"item_name": ["Item Name", "item name"],
			"description": ["Description", "description"],
			"qty": ["Quantity", "Qty", "quantity"],
			"rate": ["Rate", "rate"],
			"line_number": ["Line Number", "Line #", "line number"],
			"supplier_invoice": ["Purchase Invoice Number", "Supplier Invoice No.", "Invoice No", "Supplier Invoice No", "Supplier Invoice #", "supplier invoice no."],
			"bill_date": ["Date", "Invoice Date", "Purchase Invoice Date", "invoice date"]
		}
		for idx, cell in enumerate(header_row):
			if not cell: continue
			clean = str(cell).strip().lower()
			for key, aliases in expected.items():
				if any(alias.lower() == clean for alias in aliases):
					col_map[key] = idx
		
		if "item_code" not in col_map:
			frappe.throw(_("Could not find 'Item Code' column in Excel file. Please check column headers."))
			
		doc.set("shipment_items", [])
		
		for row in sheet.iter_rows(min_row=2, values_only=True):
			if not any(row): continue
			
			item_code = row[col_map.get("item_code")] if "item_code" in col_map else ""
			if not item_code: continue
			
			child = doc.append("shipment_items", {})
			child.item_code = str(item_code).strip()
			if "item_name" in col_map: child.item_name = str(row[col_map["item_name"]] or "").strip()
			if "description" in col_map: child.description = str(row[col_map["description"]] or "").strip()
			if "qty" in col_map: child.qty = flt(row[col_map["qty"]])
			if "rate" in col_map: child.rate = flt(row[col_map["rate"]])
			
			if "line_number" in col_map:
				lv = row[col_map["line_number"]]
				child.line_number = str(lv).strip() if lv else ""
				
			if "supplier_invoice" in col_map:
				sv = row[col_map["supplier_invoice"]]
				child.supplier_invoice = str(sv).strip() if sv else ""
				
			if "bill_date" in col_map:
				raw_date = row[col_map["bill_date"]]
				if isinstance(raw_date, (datetime.datetime, datetime.date)):
					child.bill_date = raw_date.strftime("%Y-%m-%d")
				elif isinstance(raw_date, str):
					try:
						child.bill_date = getdate(raw_date).strftime("%Y-%m-%d")
					except:
						pass
						
		doc.save()
		return "Success"
		
	except Exception as e:
		frappe.throw(f"Failed to parse Excel: {str(e)}")
