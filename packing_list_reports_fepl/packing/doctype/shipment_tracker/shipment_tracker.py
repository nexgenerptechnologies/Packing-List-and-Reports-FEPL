import frappe
from frappe.model.document import Document

class ShipmentTracker(Document):
	pass

@frappe.whitelist()
def get_outstanding_po_items(supplier, purchase_orders=None):
	if isinstance(purchase_orders, str):
		import json
		purchase_orders = json.loads(purchase_orders)
		
	conditions = ""
	if purchase_orders:
		conditions = " AND poi.parent IN ({0})".format(", ".join(["'{0}'".format(d) for d in purchase_orders]))

	return frappe.db.sql("""
		SELECT 
			poi.item_code, 
			poi.item_name, 
			poi.description, 
			(poi.qty - poi.received_qty) as qty, 
			poi.rate, 
			poi.custom_line_number,
			poi.parent as purchase_order,
			poi.name as purchase_order_item
		FROM `tabPurchase Order Item` poi
		JOIN `tabPurchase Order` po ON poi.parent = po.name
		WHERE po.supplier = %s
		AND po.docstatus = 1
		AND poi.qty > poi.received_qty
		{conditions}
		ORDER BY po.transaction_date ASC
	""".format(conditions=conditions), (supplier), as_dict=1)
