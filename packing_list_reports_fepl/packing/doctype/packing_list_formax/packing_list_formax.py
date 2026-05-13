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
    
    # We will provide a unified sheet for the Packing List
    data = [["TYPE", "Item Code", "Item Name", "Description", "Quantity", "CPN", "Box Number", "Sticker Info"]]
    
    # Part 1: Main Packing List
    for item in doc.items:
        data.append([
            "LIST", item.item_code, item.item_name, item.description, 
            item.quantity, item.custom_cpn, item.box_number, ""
        ])
    
    data.append([]) # Gap
    data.append(["STICKER DATA (Expanded)"])
    data.append(["Item Code", "CPN", "Sticker No", "Total", "Box Qty"])
    
    # Part 2: Sticker Breakdown
    for item in doc.items:
        total_qty = item.quantity
        std_qty = frappe.db.get_value('Item', item.item_code, 'custom_standard_packing_qty') or 1
        num_stickers = int(math.ceil(total_qty / std_qty))
        
        for i in range(num_stickers):
            box_qty = std_qty if i + 1 < num_stickers else (total_qty - (std_qty * i))
            data.append([
                item.item_code, item.custom_cpn, i + 1, num_stickers, box_qty
            ])

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
            @page { margin: 0; }
            body { margin: 0; padding: 20px; font-family: sans-serif; }
            .page-break { page-break-after: always; }
            .card { border: 2px solid #000; padding: 20px; margin: auto; position: relative; }
            .sticker { width: 350px; height: 250px; }
            .label { width: 500px; height: 350px; }
            .header { font-size: 1.2em; font-weight: bold; text-align: center; border-bottom: 2px solid #000; margin-bottom: 15px; }
            .row { margin-bottom: 10px; font-size: 1.1em; }
            .tag { font-weight: bold; width: 100px; display: inline-block; }
            .footer-qty { position: absolute; bottom: 20px; right: 20px; font-size: 1.5em; font-weight: bold; }
        </style>
    </head>
    <body onload="window.print()">
    """
    
    if print_type == 'Stickers':
        for item in doc.items:
            total_qty = item.quantity
            std_qty = frappe.db.get_value('Item', item.item_code, 'custom_standard_packing_qty') or 1
            num_stickers = int(math.ceil(total_qty / std_qty))
            
            for i in range(num_stickers):
                box_qty = std_qty if i + 1 < num_stickers else (total_qty - (std_qty * i))
                html += f"""
                <div class="page-break" style="display: flex; height: 100vh; align-items: center; justify-content: center;">
                    <div class="card sticker">
                        <div class="header">PACKING STICKER ({i+1} / {num_stickers})</div>
                        <div class="row"><span class="tag">Item:</span> {item.item_code}</div>
                        <div class="row"><span class="tag">Name:</span> {item.item_name}</div>
                        <div class="row"><span class="tag">CPN:</span> {item.custom_cpn or 'N/A'}</div>
                        <div class="row"><span class="tag">Box No:</span> {item.box_number or 'N/A'}</div>
                        <div class="footer-qty">QTY: {box_qty}</div>
                    </div>
                </div>
                """
    else: # Labels
        for item in doc.items:
            html += f"""
            <div class="page-break" style="display: flex; height: 100vh; align-items: center; justify-content: center;">
                <div class="card label">
                    <div class="header" style="font-size: 1.5em;">ITEM LABEL</div>
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
