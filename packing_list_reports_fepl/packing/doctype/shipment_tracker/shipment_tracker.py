import frappe
from frappe.model.document import Document

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
			poi.custom_line_number
		FROM `tabPurchase Order Item` poi
		JOIN `tabPurchase Order` po ON poi.parent = po.name
		WHERE po.supplier = %s
		AND po.name IN ({0})
		AND po.docstatus = 1
		AND poi.qty > poi.received_qty
		ORDER BY po.name, poi.idx ASC
	""".format(", ".join(["'{0}'".format(d) for d in purchase_orders])), (supplier), as_dict=1)
