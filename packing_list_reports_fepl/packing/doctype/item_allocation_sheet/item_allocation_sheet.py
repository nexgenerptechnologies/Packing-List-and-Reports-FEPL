import frappe
from frappe.model.document import Document

class ItemAllocationSheet(Document):
	pass

@frappe.whitelist()
def process_excel_upload(docname):
	doc = frappe.get_doc("Item Allocation Sheet", docname)
	if not doc.excel_file:
		return False
		
	# Placeholder for advanced Excel parsing logic
	# In a real environment, we use openpyxl or similar to parse the matrix
	# For now, we enable the structure
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
