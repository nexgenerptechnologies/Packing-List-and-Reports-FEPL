import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc

class ShipmentTracker(Document):
	pass

@frappe.whitelist()
def get_outstanding_po_items(supplier, purchase_orders):
	if isinstance(purchase_orders, str):
		import json
		purchase_orders = json.loads(purchase_orders)
		
	if not purchase_orders:
		return []

	return frappe.db.sql("""
		SELECT 
			poi.item_code, 
			poi.item_name, 
			poi.description, 
			(poi.qty - poi.received_qty) as qty, 
			poi.rate, 
			poi.custom_line_number,
			poi.parent as purchase_order,
			poi.name as purchase_order_item,
			po.currency
		FROM `tabPurchase Order Item` poi
		JOIN `tabPurchase Order` po ON poi.parent = po.name
		WHERE po.supplier = %s
		AND po.name IN ({0})
		AND po.docstatus = 1
		AND poi.qty > poi.received_qty
		ORDER BY po.name, poi.idx ASC
	""".format(", ".join(["'{0}'".format(d) for d in purchase_orders])), (supplier), as_dict=1)

@frappe.whitelist()
def make_purchase_receipt(docname):
	source_doc = frappe.get_doc("Shipment Tracker", docname)
	target_doc = frappe.new_doc("Purchase Receipt")
	target_doc.supplier = source_doc.supplier
	
	company = None
	if source_doc.shipment_items:
		for item in source_doc.shipment_items:
			if item.purchase_order:
				company = frappe.db.get_value("Purchase Order", item.purchase_order, "company")
				if company: break
					
	target_doc.company = company or frappe.defaults.get_global_default("company")
	target_doc.posting_date = frappe.utils.nowdate()
	target_doc.currency = source_doc.currency
	
	for item in source_doc.shipment_items:
		if item.qty > 0:
			pr_item = target_doc.append("items", {})
			pr_item.item_code = item.item_code
			pr_item.qty = item.qty
			pr_item.rate = item.rate
			pr_item.purchase_order = item.purchase_order
			pr_item.purchase_order_item = item.purchase_order_item
			
			if item.purchase_order_item:
				po_data = frappe.db.get_value("Purchase Order Item", item.purchase_order_item, ["uom", "stock_uom", "conversion_factor"], as_dict=1)
				if po_data:
					pr_item.uom = po_data.uom
					pr_item.stock_uom = po_data.stock_uom
					pr_item.conversion_factor = po_data.conversion_factor
					
	target_doc.insert()
	return target_doc.name

@frappe.whitelist()
def create_purchase_invoices(docname):
	source_doc = frappe.get_doc("Shipment Tracker", docname)
	if not source_doc.purchase_receipt:
		frappe.throw("Please link a Purchase Receipt first.")
		
	created_invoices = []
	for row in source_doc.shipment_invoices:
		if not row.purchase_invoice:
			# Create PI from PR
			from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
			pi = make_purchase_invoice(source_doc.purchase_receipt)
			pi.bill_no = row.bill_no
			pi.bill_date = row.bill_date
			pi.insert()
			
			row.db_set("purchase_invoice", pi.name)
			created_invoices.append(pi.name)
			
	return created_invoices
