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
			if not row.stock_reservation_entry:
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
