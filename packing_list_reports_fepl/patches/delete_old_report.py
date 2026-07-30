import frappe

def execute():
    if frappe.db.exists("Report", "Supplier RFQ Export"):
        frappe.delete_doc("Report", "Supplier RFQ Export", ignore_missing=True)