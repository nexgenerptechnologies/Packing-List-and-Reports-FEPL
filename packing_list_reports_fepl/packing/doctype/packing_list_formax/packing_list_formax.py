import frappe
from frappe.model.document import Document
from frappe import _

class PackingListFormax(Document):
    pass

    def validate(self):
        self.calculate_total_quantity()

    def calculate_total_quantity(self):
        self.total_quantity = 0
        for item in self.items:
            self.total_quantity += float(item.quantity or 0)

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
def download_excel(docname, export_type):
    import math
    doc = frappe.get_doc('Packing List Formax', docname)
    data = []
    filename = f"{doc.name}_{export_type}.xlsx"
    
    if export_type == 'Packing List':
        data = [["Item Name", "Description", "Quantity", "CPN", "Box Number"]]
        for item in doc.items:
            data.append([item.item_name, item.description, item.quantity, item.custom_cpn, item.box_number])
            
    elif export_type == 'Stickers':
        data = [["CPN STICKER GRID (6 Columns)"]]
        for item in doc.items:
            total_qty = float(item.quantity or 0)
            std_val = frappe.db.get_value('Item', item.item_code, 'custom_standard_packing_qty')
            std_qty = float(std_val) if std_val else total_qty
            if std_qty <= 0: std_qty = total_qty
            num_stickers = int(math.ceil(total_qty / std_qty))
            
            data.append([f"Item: {item.item_name} (Total: {num_stickers})"])
            current_row = []
            for i in range(num_stickers):
                current_row.append(item.custom_cpn or "")
                if len(current_row) == 6:
                    data.append(current_row)
                    current_row = []
            if current_row:
                current_row += [""] * (6 - len(current_row))
                data.append(current_row)
            data.append([]) 
            
    elif export_type == 'Labels':
        data = [["Box No", "Customer", "Invoice", "Item Details"]]
        boxes = {}
        for item in doc.items:
            b_no = item.box_number or "N/A"
            if b_no not in boxes: boxes[b_no] = []
            boxes[b_no].append(item)
            
        for b_no in sorted(boxes.keys()):
            # For Excel, we list each item in the box as a separate line or combined?
            # Combined summary is usually clearer for a single row.
            items_summary = "; ".join([f"{i.item_name} [Qty: {i.quantity}, CPN: {i.custom_cpn}]" for i in boxes[b_no]])
            data.append([b_no, doc.customer_name, doc.sales_invoice, items_summary])

    from frappe.utils.xlsxutils import make_xlsx
    xlsx_file = make_xlsx(data, export_type)
    
    frappe.response['filename'] = filename
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
            @page { size: A4; margin: 5mm; }
            body { margin: 0; padding: 0; font-family: sans-serif; }
            .grid-container { display: flex; flex-wrap: wrap; width: 200mm; margin: auto; }
            .label-box { 
                width: 95mm; 
                min-height: 68mm; 
                border: 2px solid #000; 
                margin: 2mm; 
                padding: 10px; 
                box-sizing: border-box;
                display: flex;
                flex-direction: column;
            }
            .sticker-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
            .sticker-td { border: 1px solid #000; padding: 5px; text-align: center; font-weight: bold; font-size: 12px; }
            .header-text { font-size: 1.1em; font-weight: bold; text-align: center; border-bottom: 2px solid #000; margin-bottom: 10px; padding-bottom: 5px; white-space: nowrap; }
            .field-row { font-size: 0.9em; margin-bottom: 4px; }
            .field-tag { font-weight: bold; width: 80px; display: inline-block; }
            .item-table { width: 100%; border-collapse: collapse; margin-top: 5px; font-size: 0.75em; table-layout: fixed; }
            .item-table th, .item-table td { border: 1px solid #333; padding: 2px; text-align: left; word-wrap: break-word; }
            .col-name { width: 28%; }
            .col-desc { width: 33%; }
            .col-qty { width: 19%; text-align: center !important; }
            .col-cpn { width: 20%; text-align: center !important; }
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
            
            html += f'<div style="margin-bottom: 20px;">'
            html += f'<div style="font-weight:bold; background:#eee; padding:5px; border:1px solid #000;">Item: {item.item_name}</div>'
            html += '<table class="sticker-table"><tr>'
            for i in range(num_stickers):
                html += f'<td class="sticker-td">{item.custom_cpn or ""}</td>'
                if (i + 1) % 6 == 0 and (i + 1) < num_stickers:
                    html += '</tr><tr>'
            remainder = num_stickers % 6
            if remainder != 0:
                for _ in range(6 - remainder): html += '<td class="sticker-td"></td>'
            html += '</tr></table></div>'
    else: # Labels - Grouped by Box, 8 per A4
        boxes = {}
        for item in doc.items:
            b_no = item.box_number or "N/A"
            if b_no not in boxes: boxes[b_no] = []
            boxes[b_no].append(item)
            
        html += '<div class="grid-container">'
        for b_no in sorted(boxes.keys()):
            html += f"""
            <div class="label-box">
                <div class="header-text">FORMAX ELCTRONICS PVT. LTD.</div>
                <div class="field-row"><span class="field-tag">Customer:</span> {doc.customer_name}</div>
                <div class="field-row"><span class="field-tag">Invoice:</span> {doc.sales_invoice}</div>
                <div class="field-row"><span class="field-tag">Box No:</span> {b_no}</div>
                <table class="item-table">
                    <thead>
                        <tr>
                            <th class="col-name">Item Name</th>
                            <th class="col-desc">Description</th>
                            <th class="col-qty">Qty</th>
                            <th class="col-cpn">CPN</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            box_total = 0
            for itm in boxes[b_no]:
                # Format qty to remove .0 if it is a whole number
                display_qty = int(itm.quantity) if itm.quantity == int(itm.quantity) else itm.quantity
                box_total += float(itm.quantity or 0)
                html += f"""
                <tr>
                    <td>{itm.item_name}</td>
                    <td>{itm.description or ""}</td>
                    <td style="text-align:center;">{display_qty}</td>
                    <td style="text-align:center;">{itm.custom_cpn or ""}</td>
                </tr>
                """
            
            # Format box_total to remove .0
            display_box_total = int(box_total) if box_total == int(box_total) else box_total
            html += f"""
                <tr style="background:#f9f9f9; font-weight:bold;">
                    <td colspan="2" style="text-align:right;">Total Qty in Box:</td>
                    <td style="text-align:center;">{display_box_total}</td>
                    <td></td>
                </tr>
            """
            html += "</tbody></table></div>"
        html += "</div>"
            
    html += "</body></html>"
    return html
