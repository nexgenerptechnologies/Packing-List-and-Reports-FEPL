import frappe
from frappe.model.document import Document
from frappe import _

class PackingListFormax(Document):
    pass

@frappe.whitelist()
def get_items_from_si(doctype, txt, searchfield, start, page_len, filters):
    sales_invoice = filters.get('sales_invoice')
    if not sales_invoice:
        return []

    return frappe.db.sql("""
        SELECT item_code, item_name 
        FROM `tabSales Invoice Item` 
        WHERE parent = %s AND item_code LIKE %s
        ORDER BY item_code ASC
        LIMIT %s, %s
    """, (sales_invoice, f"%{txt}%", start, page_len))

@frappe.whitelist()
def get_si_item_details(sales_invoice, item_code):
    if not sales_invoice or not item_code:
        return {}

    # Fetching the first matching item from the Sales Invoice
    item_details = frappe.db.get_value('Sales Invoice Item', 
        {'parent': sales_invoice, 'item_code': item_code}, 
        ['item_name', 'description', 'qty', 'custom_cpn'], as_dict=1)
    
    return item_details

@frappe.whitelist()
def get_sticker_data(docname):
    """
    Returns data for stickers calculation.
    Stickers = Sales Invoice Qty / custom_standard_packing_qty
    """
    doc = frappe.get_doc('Packing List Formax', docname)
    sticker_data = []

    for item in doc.items:
        # Get Sales Invoice Qty and Standard Packing Qty
        si_qty = item.quantity
        
        # Get standard packing qty from Item master
        std_packing_qty = frappe.db.get_value('Item', item.item_code, 'custom_standard_packing_qty') or 1
        
        num_stickers = 0
        if std_packing_qty > 0:
            import math
            num_stickers = math.ceil(si_qty / std_packing_qty)
        
        sticker_data.append({
            'item_code': item.item_code,
            'item_name': item.item_name,
            'num_stickers': num_stickers,
            'description': item.description,
            'custom_cpn': item.custom_cpn
        })
    
    return sticker_data
