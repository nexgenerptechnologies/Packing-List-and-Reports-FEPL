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
    import math
    doc = frappe.get_doc('Packing List Formax', docname)
    
    # Sheet 1: Main Packing List
    data = [["TYPE", "Item Code", "Item Name", "Description", "Quantity", "CPN", "Box Number"]]
    for item in doc.items:
        data.append([
            "LIST", item.item_code, item.item_name, item.description, 
            item.quantity, item.custom_cpn, item.box_number
        ])
    
    data.append([]) # Gap
    data.append(["CPN STICKER GRID (6 Columns)"])
    
    # Part 2: 6-Column CPN Grid
    for item in doc.items:
        total_qty = float(item.quantity or 0)
        std_val = frappe.db.get_value('Item', item.item_code, 'custom_standard_packing_qty')
        std_qty = float(std_val) if std_val else total_qty
        if std_qty <= 0: std_qty = total_qty
        
        num_stickers = int(math.ceil(total_qty / std_qty))
        
        # Header for the item group
        data.append([f"Item: {item.item_code} (Total: {num_stickers})"])
        
        # Create 6-column rows
        current_row = []
        for i in range(num_stickers):
            current_row.append(item.custom_cpn or "")
            if len(current_row) == 6:
                data.append(current_row)
                current_row = []
        if current_row:
            # Fill remaining columns with empty strings
            current_row += [""] * (6 - len(current_row))
            data.append(current_row)
        data.append([]) # Gap between items

    from frappe.utils.xlsxutils import make_xlsx
    xlsx_file = make_xlsx(data, "Packing_Data")
    
    frappe.response['filename'] = f"{doc.name}_Packing_Data.xlsx"
    frappe.response['filecontent'] = xlsx_file.getvalue()
    frappe.response['type'] = 'binary'

@frappe.whitelist()
def get_print_html(docname, print_type):
    import math
    doc = frappe.get_doc('Packing List Formax', docname)
    
    html = """
    <html>
    <head>
        <style>
            @page { margin: 5mm; }
            body { margin: 0; padding: 10px; font-family: sans-serif; }
            table { width: 100%; border-collapse: collapse; table-layout: fixed; }
            td { border: 1px solid #000; padding: 8px; text-align: center; font-weight: bold; font-size: 14px; word-break: break-all; }
            .item-section { margin-bottom: 20px; }
            .item-header { background: #eee; padding: 5px; font-weight: bold; border: 1px solid #000; margin-bottom: -1px; }
            
            /* For Labels (unchanged logic, just size) */
            .page-break { page-break-after: always; }
            .card { border: 2px solid #000; padding: 30px; margin: auto; position: relative; width: 600px; height: 400px; }
            .header { font-size: 1.5em; font-weight: bold; text-align: center; border-bottom: 3px solid #000; margin-bottom: 20px; padding-bottom: 10px; }
            .row { margin-bottom: 15px; font-size: 1.3em; }
            .tag { font-weight: bold; width: 140px; display: inline-block; }
            .footer-qty { position: absolute; bottom: 30px; right: 30px; font-size: 2em; font-weight: bold; }
        </style>
    </head>
    <body onload="window.print()">
    """
    
    if print_type == 'Stickers':
        for item in doc.items:
            total_qty = float(item.quantity or 0)
            std_val = frappe.db.get_value('Item', item.item_code, 'custom_standard_packing_qty')
            std_qty = float(std_val) if std_val else total_qty
            if std_qty <= 0: std_qty = total_qty
            
            num_stickers = int(math.ceil(total_qty / std_qty))
            
            html += f'<div class="item-section">'
            html += f'<div class="item-header">Item: {item.item_code} (Stickers: {num_stickers})</div>'
            html += '<table><tr>'
            
            for i in range(num_stickers):
                html += f'<td>{item.custom_cpn or ""}</td>'
                if (i + 1) % 6 == 0 and (i + 1) < num_stickers:
                    html += '</tr><tr>'
            
            # Fill empty cells to complete the last row
            remainder = num_stickers % 6
            if remainder != 0:
                for _ in range(6 - remainder):
                    html += '<td></td>'
            
            html += '</tr></table></div>'
    else: # Labels
        for item in doc.items:
            html += f"""
            <div class="page-break" style="display: flex; height: 100vh; align-items: center; justify-content: center;">
                <div class="card">
                    <div class="header">ITEM LABEL</div>
                    <div class="row"><span class="tag">Customer:</span> {doc.customer_name}</div>
                    <div class="row"><span class="tag">Invoice:</span> {doc.sales_invoice}</div>
                    <hr>
                    <div class="row"><span class="tag">Item Code:</span> {item.item_code}</div>
                    <div class="row"><span class="tag">Item Name:</span> {item.item_name}</div>
                    <div class="row"><span class="tag">CPN:</span> {item.custom_cpn or 'N/A'}</div>
                    <div class="row"><span class="tag">Total Qty:</span> {item.quantity}</div>
                    <div class="row"><span class="tag">Box No:</span> {item.box_number or 'N/A'}</div>
                </div>
            </div>
            """
            
    html += "</body></html>"
    return html
