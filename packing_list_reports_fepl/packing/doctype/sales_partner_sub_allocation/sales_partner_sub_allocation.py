import frappe
from frappe.model.document import Document
from frappe.utils import flt

class SalesPartnerSubAllocation(Document):
	def validate(self):
		self.validate_quotas()

	def on_submit(self):
		self.create_stock_reservations()

	def on_cancel(self):
		self.cancel_stock_reservations()

	def validate_quotas(self):
		# Validation logic to ensure SP doesn't allocate more than the TL gave them for each item
		pass

	def create_stock_reservations(self):
		for row in self.sub_allocations:
			if row.allocated_qty > 0 and row.sales_order and not row.stock_reservation_entry:
				so_item = frappe.db.get_value("Sales Order Item", 
					{"parent": row.sales_order, "item_code": row.item_code}, "name")
				
				if so_item:
					sre = frappe.get_doc({
						"doctype": "Stock Reservation Entry",
						"item_code": row.item_code,
						"warehouse": "Finished Goods",
						"voucher_type": "Sales Order",
						"voucher_no": row.sales_order,
						"voucher_detail_no": so_item,
						"reserved_qty": row.allocated_qty,
						"company": frappe.db.get_value("Sales Order", row.sales_order, "company"),
						"status": "Reserved"
					})
					sre.insert()
					sre.submit()
					row.db_set("stock_reservation_entry", sre.name)

	def cancel_stock_reservations(self):
		for row in self.sub_allocations:
			if row.stock_reservation_entry:
				sre_status = frappe.db.get_value("Stock Reservation Entry", row.stock_reservation_entry, "docstatus")
				if sre_status == 1:
					sre = frappe.get_doc("Stock Reservation Entry", row.stock_reservation_entry)
					sre.cancel()
				row.db_set("stock_reservation_entry", None)

@frappe.whitelist()
def get_partner_quotas(sales_partner):
	return frappe.db.sql("""
		SELECT 
			ad.item_code, 
			ad.item_name, 
			ad.description, 
			SUM(ad.allocated_qty) as allocated_qty
		FROM `tabItem Allocation Sheet` ias
		JOIN `tabPartner Allocation Detail` ad ON ad.parent = ias.name
		WHERE ias.docstatus = 1
		AND ad.sales_partner = %s
		GROUP BY ad.item_code, ad.item_name, ad.description
	""", (sales_partner), as_dict=1)
