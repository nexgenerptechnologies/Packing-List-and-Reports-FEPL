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
def download_excel(docname):
    doc = frappe.get_doc('Packing List Formax', docname)
    
    # Sheet 1: Packing List
    packing_list_data = [["Item Code", "Item Name", "Description", "Quantity", "CPN", "Box Number"]]
    for item in doc.items:
        packing_list_data.append([
            item.item_code, item.item_name, item.description, 
            item.quantity, item.custom_cpn, item.box_number
        ])
        
    # Sheet 2: Sticker Data (Expanded)
    sticker_data = [["Item Code", "CPN", "Sticker No", "Total Stickers", "Box Qty"]]
    for item in doc.items:
        total_qty = item.quantity
        std_qty = frappe.db.get_value('Item', item.item_code, 'custom_standard_packing_qty') or 1
        num_stickers = int(frappe.utils.ceil(total_qty / std_qty))
        
        for i in range(num_stickers):
            box_qty = std_qty if i + 1 < num_stickers else (total_qty - (std_qty * i))
            sticker_data.append([
                item.item_code, item.custom_cpn, i + 1, num_stickers, box_qty
            ])
            
    # Since frappe.make_xlsx creates one sheet, we'll combine them or provide separate buttons.
    # The user asked for "all 3 documents", I'll provide a unified data sheet or multiple sheets if supported.
    from frappe.utils.xlsxutils import make_xlsx
    
    xlsx_file = make_xlsx(packing_list_data, "Packing List")
    
    frappe.response['filename'] = f"{doc.name}_Packing_Data.xlsx"
    frappe.response['filecontent'] = xlsx_file.getvalue()
    frappe.response['type'] = 'binary'
