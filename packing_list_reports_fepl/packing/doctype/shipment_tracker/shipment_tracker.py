import frappe
from frappe.model.document import Document
from frappe import _

class ShipmentTracker(Document):
	def before_submit(self):
		if not self.shipment_items or len(self.shipment_items) == 0:
			frappe.throw(_("Please fetch or add items to the shipment before submitting."))

@frappe.whitelist()
def get_outstanding_po_items(supplier, purchase_orders):
	if isinstance(purchase_orders, str):
		import json
		purchase_orders = json.loads(purchase_orders)
		
	if not purchase_orders:
		return []

	return frappe.db.sql("""
		SELECT 
			poi.item_code, poi.item_name, poi.description, 
			(poi.qty - poi.received_qty) as qty, poi.rate, 
			COALESCE(NULLIF(poi.custom_line_number, ''), poi.line_number) as line_number,
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
	
	# Initial data from first item
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
			# STRICT VALIDATION against PO Item
			if not item.purchase_order_item:
				frappe.throw(_("Row {0}: Item {1} is not linked to any Purchase Order Item. Please Fetch Pending Orders again.").format(item.idx, item.item_code))
			
			po_item = frappe.get_doc("Purchase Order Item", item.purchase_order_item)
			po_line_number = po_item.custom_line_number or po_item.line_number
			
			# Check discrepancy
			discrepancies = []
			if item.item_code != po_item.item_code: discrepancies.append(_("Item Code mismatch (Expected: {0}, Got: {1})").format(po_item.item_code, item.item_code))
			if item.qty > (po_item.qty - po_item.received_qty): discrepancies.append(_("Quantity exceeds pending amount (Pending: {0}, Got: {1})").format(po_item.qty - po_item.received_qty, item.qty))
			if abs(float(item.rate) - float(po_item.rate)) > 0.01: discrepancies.append(_("Rate mismatch (Expected: {0}, Got: {1})").format(po_item.rate, item.rate))
			if str(item.line_number) != str(po_line_number): discrepancies.append(_("Line Number mismatch (Expected: {0}, Got: {1})").format(po_line_number, item.line_number))
			
			if discrepancies:
				frappe.throw(_("Row {0}: Validation Failed for Item {1}.\n{2}").format(item.idx, item.item_code, "\n".join(discrepancies)))

			# Populate PR item
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
		new_items = [pi_item for pi_item in pi.get("items") if pi_item.purchase_order_item in group_po_items]
		pi.set("items", new_items)
		
		if pi.get("items"):
			pi.insert()
			created_invoices.append(pi.name)
			for row in source_doc.shipment_invoices:
				if row.bill_no == inv_no:
					row.db_set("purchase_invoice", pi.name)
					break
					
	return created_invoices
