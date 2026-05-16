import frappe
from frappe.model.document import Document

class ShipmentTracker(Document):
	pass

@frappe.whitelist()
def get_outstanding_po_items(supplier, purchase_order):
	return frappe.db.sql("""
		SELECT 
			poi.item_code, 
			poi.item_name, 
			poi.description, 
			(poi.qty - poi.received_qty) as qty, 
			poi.rate, 
			poi.custom_line_number
		FROM `tabPurchase Order Item` poi
		JOIN `tabPurchase Order` po ON poi.parent = po.name
		WHERE po.supplier = %s
		AND po.name = %s
		AND po.docstatus = 1
		AND poi.qty > poi.received_qty
		ORDER BY poi.idx ASC
	""", (supplier, purchase_order), as_dict=1)
