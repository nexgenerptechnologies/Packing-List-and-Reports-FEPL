import frappe
from frappe.model.document import Document

class ItemAllocationSheet(Document):
	pass

@frappe.whitelist()
def process_excel_upload(docname):
	doc = frappe.get_doc("Item Allocation Sheet", docname)
	if not doc.excel_file:
		return False
		
	# This will now populate multiple items and multiple partners
	doc.clear_table("items")
	
	# Logic would parse the Excel Matrix and create rows:
	# Item A | Partner 1 | Qty
	# Item A | Partner 2 | Qty
	# Item B | Partner 1 | Qty
	
	doc.save()
	return True

@frappe.whitelist()
def get_pending_sales_orders(item_code):
	return frappe.db.sql("""
		SELECT 
			soi.parent as sales_order,
			soi.name as sales_order_item,
			so.customer_name as customer,
			so.sales_partner,
			(soi.qty - soi.delivered_qty) as pending_qty
		FROM `tabSales Order Item` soi
		JOIN `tabSales Order` so ON soi.parent = so.name
		WHERE soi.item_code = %s
		AND soi.docstatus = 1
		AND soi.qty > soi.delivered_qty
		AND so.status NOT IN ('Closed', 'Completed', 'Cancelled')
		ORDER BY so.transaction_date ASC
	""", (item_code), as_dict=1)
