import frappe
from frappe.model.document import Document

class PackingListSettings(Document):
	pass

def update_po_line_numbers(doc, method=None):
	if not frappe.db.get_single_value('Packing List Settings', 'enable_po_line_numbering'):
		return

	import re
	name = doc.name
	if not name:
		return

	segments = re.split(r'[^a-zA-Z0-9]', name)
	numeric_segments = [s for s in segments if s.isdigit()]
	if numeric_segments:
		po_seq = numeric_segments[-1]
	else:
		po_seq = name

	meta = frappe.get_meta('Purchase Order Item')
	fields_to_update = []
	if meta.has_field('line_number'):
		fields_to_update.append('line_number')
	if meta.has_field('custom_line_number'):
		fields_to_update.append('custom_line_number')

	if not fields_to_update:
		return

	for item in doc.items:
		for field in fields_to_update:
			current_val = item.get(field)
			if not current_val or not str(current_val).strip():
				item.set(field, f'{po_seq}-{item.idx}')

@frappe.whitelist()
def get_po_items(purchase_order):
	if not frappe.db.get_single_value("Packing List Settings", "enable_get_specific_items"):
		frappe.throw("Get Specific Items feature is disabled in Packing List Settings.")

	po = frappe.get_doc("Purchase Order", purchase_order)
	meta = frappe.get_meta("Purchase Order Item")
	
	has_ln = meta.has_field("line_number")
	has_cln = meta.has_field("custom_line_number")

	items = []
	for item in po.items:
		ln_val = None
		if has_ln:
			ln_val = item.get("line_number")
		if not ln_val and has_cln:
			ln_val = item.get("custom_line_number")

		items.append({
			"item_code": item.item_code,
			"item_name": item.item_name,
			"description": item.description or "",
			"qty": item.qty,
			"uom": item.uom,
			"warehouse": item.warehouse,
			"rate": item.rate,
			"name": item.name,
			"line_number": ln_val or ""
		})
	return items

@frappe.whitelist()
def get_so_items(customer, sales_order=None, item_code=None, item_name=None, description=None):
	if not frappe.db.get_single_value("Packing List Settings", "enable_get_specific_items_dn"):
		frappe.throw("Get Specific Items for Delivery Note feature is disabled in Packing List Settings.")

	if not customer:
		frappe.throw("Customer is required.")

	if not (sales_order or item_code or item_name or description):
		return []

	filters = {
		"customer": customer,
		"docstatus": 1,
		"per_delivered": ["<", 100]
	}
	if sales_order:
		filters["name"] = sales_order

	sales_orders = frappe.get_all("Sales Order", filters=filters, fields=["name"], limit=100)
	if not sales_orders:
		return []

	so_names = [so.name for so in sales_orders]

	item_filters = {
		"parent": ["in", so_names],
		"docstatus": 1
	}
	if item_code:
		item_filters["item_code"] = item_code

	so_items = frappe.get_all(
		"Sales Order Item",
		filters=item_filters,
		fields=[
			"item_code", "item_name", "description", "qty", "delivered_qty", 
			"stock_uom", "warehouse", "rate", "name as so_detail", "parent as sales_order"
		]
	)

	all_items = []
	for item in so_items:
		if item_name and item_name.lower() not in (item.get("item_name") or "").lower():
			continue
		if description and description.lower() not in (item.get("description") or "").lower():
			continue

		qty = float(item.get("qty") or 0)
		delivered_qty = float(item.get("delivered_qty") or 0)
		qty_to_deliver = qty - delivered_qty
		if qty_to_deliver > 0:
			all_items.append({
				"checked": False,
				"item_code": item.item_code,
				"item_name": item.item_name,
				"description": item.description or "",
				"qty_to_deliver": qty_to_deliver,
				"delivered_qty": delivered_qty,
				"uom": item.stock_uom or item.get("uom"),
				"warehouse": item.warehouse,
				"rate": item.rate,
				"sales_order": item.sales_order,
				"so_detail": item.so_detail
			})

	return all_items
