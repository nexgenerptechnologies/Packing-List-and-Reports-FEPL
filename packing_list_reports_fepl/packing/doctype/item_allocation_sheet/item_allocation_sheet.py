import frappe
from frappe.model.document import Document
from frappe.utils import flt

class ItemAllocationSheet(Document):
	def on_submit(self):
		self.create_stock_reservations()

	def on_cancel(self):
		self.cancel_stock_reservations()

	def create_stock_reservations(self):
		for row in self.allocations:
			if row.allocated_qty > 0 and not row.stock_reservation_entry:
				sre = frappe.get_doc({
					"doctype": "Stock Reservation Entry",
					"item_code": self.item_code,
					"warehouse": self.warehouse,
					"voucher_type": "Sales Order",
					"voucher_no": row.sales_order,
					"voucher_detail_no": row.sales_order_item,
					"reserved_qty": row.allocated_qty,
					"company": frappe.db.get_value("Sales Order", row.sales_order, "company") or frappe.defaults.get_global_default("company"),
					"status": "Reserved"
				})
				sre.insert()
				sre.submit()
				row.db_set("stock_reservation_entry", sre.name)

	def cancel_stock_reservations(self):
		for row in self.allocations:
			if row.stock_reservation_entry:
				sre_status = frappe.db.get_value("Stock Reservation Entry", row.stock_reservation_entry, "docstatus")
				if sre_status == 1:
					sre = frappe.get_doc("Stock Reservation Entry", row.stock_reservation_entry)
					sre.cancel()
				row.db_set("stock_reservation_entry", None)

@frappe.whitelist()
def get_allocation_for_dn(sales_orders, items):
	if isinstance(sales_orders, str):
		sales_orders = frappe.parse_json(sales_orders)
	if isinstance(items, str):
		items = frappe.parse_json(items)

	allocations = {}
	
	# We look for submitted allocation sheets containing these SOs and Items
	data = frappe.db.sql("""
		SELECT 
			ad.sales_order, 
			ias.item_code, 
			SUM(ad.allocated_qty) as total_allocated
		FROM `tabItem Allocation Sheet` ias
		JOIN `tabAllocation Detail` ad ON ad.parent = ias.name
		WHERE ias.docstatus = 1
		AND ad.sales_order IN %(sales_orders)s
		AND ias.item_code IN %(items)s
		GROUP BY ad.sales_order, ias.item_code
	""", {"sales_orders": sales_orders, "items": items}, as_dict=1)

	for row in data:
		key = f"{row.sales_order}|{row.item_code}"
		allocations[key] = row.total_allocated

	return allocations

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
