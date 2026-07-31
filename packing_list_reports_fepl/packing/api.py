import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.xlsxutils import make_xlsx

@frappe.whitelist(allow_guest=False)
def download_supplier_rfq(rfq_name):
	if not frappe.has_permission("Request for Quotation", "read"):
		frappe.throw(_("Not permitted"))

	columns = [
		{"label": "RFQ ID", "fieldname": "rfq_id"},
		{"label": "RFQ Date", "fieldname": "rfq_date"},
		{"label": "Customer Name", "fieldname": "customer_name"},
		{"label": "Project", "fieldname": "project"},
		{"label": "SOP Date", "fieldname": "sop_date"},
		{"label": "Item Code", "fieldname": "item_code"},
		{"label": "Item Name", "fieldname": "item_name"},
		{"label": "Description", "fieldname": "description"},
		{"label": "Brand", "fieldname": "brand"},
		{"label": "Monthly Qty", "fieldname": "monthly_qty"},
		{"label": "Customer Description", "fieldname": "customer_description"},
		{"label": "Sales Partner", "fieldname": "sales_partner"},
		{"label": "Stock", "fieldname": "stock_qty"},
		{"label": "Reserved Stock", "fieldname": "reserved_stock"},
		{"label": "Supplier MPN", "fieldname": "supplier_mpn"},
		{"label": "Supplier Description", "fieldname": "supplier_description"},
		{"label": "MAKE", "fieldname": "make"},
		{"label": "SPQ", "fieldname": "spq"},
		{"label": "Lead Time", "fieldname": "lead_time"},
		{"label": "Price Per 1000", "fieldname": "price_per_1000"},
		{"label": "Quote date", "fieldname": "quote_date"},
		{"label": "Remarks", "fieldname": "remarks"}
	]

	q = frappe.get_doc("Request for Quotation", rfq_name)
	
	item_codes = [d.item_code for d in q.items if d.item_code]
	stock_qty_map = {}
	reserved_stock_map = {}
	
	if item_codes:
		bin_data = frappe.db.sql("""
			SELECT item_code, SUM(actual_qty) AS stock_qty
			FROM `tabBin`
			WHERE item_code IN %s
			GROUP BY item_code
		""", (tuple(item_codes),), as_dict=1)
		stock_qty_map = {b.item_code: flt(b.stock_qty) for b in bin_data}

		reserved_data = frappe.db.sql("""
			SELECT item_code, SUM(reserved_qty - IFNULL(delivered_qty, 0)) AS reserved_qty
			FROM `tabStock Reservation Entry`
			WHERE docstatus = 1 AND item_code IN %s
			GROUP BY item_code
		""", (tuple(item_codes),), as_dict=1)
		reserved_stock_map = {r.item_code: flt(r.reserved_qty) for r in reserved_data}

	data = [[c["label"] for c in columns]]
	
	for item in q.items:
		brand = item.get("brand") or frappe.db.get_value("Item", item.item_code, "brand") or ""
		sop = item.get("custom_sop_date") or q.get("custom_sop_date") or ""
		mq = item.get("custom_monthly_qty") or item.qty or 0.0
		cd = item.get("custom_customer_description") or ""
		
		row_dict = {
			"rfq_id": q.name,
			"rfq_date": str(q.transaction_date) if q.transaction_date else "",
			"customer_name": q.get("custom_customer_name") or "",
			"project": q.get("custom_project") or "",
			"sop_date": str(sop) if sop else "",
			"item_code": item.item_code,
			"item_name": item.item_name or "",
			"description": item.description or "",
			"brand": brand,
			"monthly_qty": mq,
			"customer_description": cd,
			"sales_partner": item.get("custom_sales_partner") or "",
			"stock_qty": stock_qty_map.get(item.item_code, 0.0),
			"reserved_stock": reserved_stock_map.get(item.item_code, 0.0),
			"supplier_mpn": "",
			"supplier_description": "",
			"make": "",
			"spq": "",
			"lead_time": "",
			"price_per_1000": "",
			"quote_date": "",
			"remarks": ""
		}
		
		row_list = [row_dict.get(c["fieldname"]) for c in columns]
		data.append(row_list)

	xlsx_file = make_xlsx(data, "Supplier RFQ")
	
	frappe.response["filename"] = f"{rfq_name}_Supplier_RFQ.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "binary"
@frappe.whitelist(allow_guest=False)
def upload_supplier_excel(rfq_name, file_url):
	import openpyxl
	from frappe.utils.file_manager import get_file_path
	import datetime
	from frappe.utils import flt

	if not frappe.has_permission("Request for Quotation", "write"):
		frappe.throw(_("Not permitted"))

	file_path = get_file_path(file_url)
	
	try:
		wb = openpyxl.load_workbook(file_path, data_only=True)
		ws = wb.active
	except Exception as e:
		frappe.throw(_("Failed to read Excel file: {0}").format(str(e)))

	rfq = frappe.get_doc("Request for Quotation", rfq_name)
	
	# Find headers
	headers = [str(cell.value).strip() if cell.value else "" for cell in ws[1]]
	
	def get_idx(name):
		return headers.index(name) if name in headers else -1

	ic_idx = get_idx("Item Code")
	mpn_idx = get_idx("Supplier MPN")
	desc_idx = get_idx("Supplier Description")
	make_idx = get_idx("MAKE")
	spq_idx = get_idx("SPQ")
	lt_idx = get_idx("Lead Time")
	price_idx = get_idx("Price Per 1000")
	date_idx = get_idx("Quote date")
	remarks_idx = get_idx("Remarks")

	if ic_idx == -1:
		frappe.throw(_("Invalid Template: Missing 'Item Code' column."))

	sales_partners_to_notify = set()
	updated_items = 0

	# Update Items
	for row in ws.iter_rows(min_row=2, values_only=True):
		item_code = row[ic_idx]
		if not item_code: continue

		for item in rfq.items:
			if item.item_code == item_code:
				if mpn_idx != -1: item.custom_supplier_mpn = str(row[mpn_idx] or "")
				if desc_idx != -1: item.custom_supplier_description = str(row[desc_idx] or "")
				if make_idx != -1: item.custom_make = str(row[make_idx] or "")
				if spq_idx != -1: item.custom_spq = flt(row[spq_idx])
				if lt_idx != -1: item.custom_lead_time = str(row[lt_idx] or "")
				if price_idx != -1: item.custom_price_per_1000 = flt(row[price_idx])
				if remarks_idx != -1: item.custom_remarks = str(row[remarks_idx] or "")
				
				if date_idx != -1:
					q_date = row[date_idx]
					if isinstance(q_date, datetime.datetime):
						item.custom_quote_date = q_date.date()
					elif q_date:
						try:
							from frappe.utils import getdate
							# Try standard getdate
							item.custom_quote_date = getdate(q_date)
						except Exception:
							pass
						# If it's a string like 31/07/2026 or 31-07-2026
						if isinstance(q_date, str):
							q_str = q_date.replace('/', '-')
							parts = q_str.split('-')
							if len(parts) == 3:
								# If first part is day (e.g. 31)
								if len(parts[0]) <= 2 and int(parts[0]) > 12:
									item.custom_quote_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
								# If first part is day but <= 12, assume DD-MM-YYYY if standard
								elif len(parts[0]) <= 2 and len(parts[2]) == 4:
									item.custom_quote_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
								else:
									item.custom_quote_date = q_date
				
				if item.custom_sales_partner:
					sales_partners_to_notify.add(item.custom_sales_partner)
					
				updated_items += 1
				break
				
	if updated_items > 0:
		rfq.save(ignore_permissions=True)
		
		# Notification 2: Notify Sales Partners
		for sp_name in sales_partners_to_notify:
			# Try to find a user matching the Sales Partner name
			user_email = ""
			try:
				sp = frappe.get_doc("Sales Partner", sp_name)
				if hasattr(sp, "user") and sp.user:
					user_email = sp.user
				elif hasattr(sp, "partner_email") and sp.partner_email:
					user_email = sp.partner_email
			except Exception:
				pass
				
			if not user_email:
				user_email = frappe.db.get_value("User", {"full_name": sp_name})
			
			if user_email and frappe.db.exists("User", user_email):
				# Create Notification Log
				doc = frappe.new_doc("Notification Log")
				doc.subject = _("Supplier Pricing Uploaded for RFQ: {0}").format(rfq.name)
				doc.email_content = _("The Product Manager has uploaded supplier pricing for your requested items on {0}.").format(rfq.name)
				doc.for_user = user_email
				doc.document_type = "Request for Quotation"
				doc.document_name = rfq.name
				doc.insert(ignore_permissions=True)
				frappe.publish_realtime('notification', doc.subject, user=user_email)

	return "Success"
def notify_rfq_submit(doc, method):
	if doc.get("custom_product_manager"):
		pm_user = doc.custom_product_manager
		if frappe.db.exists("User", pm_user):
			nlog = frappe.new_doc("Notification Log")
			nlog.subject = _("New Request for Quotation: {0}").format(doc.name)
			nlog.email_content = _("A new Request for Quotation has been submitted and is ready to be sent to a supplier.")
			nlog.for_user = pm_user
			nlog.document_type = "Request for Quotation"
			nlog.document_name = doc.name
			nlog.insert(ignore_permissions=True)
			frappe.publish_realtime('notification', nlog.subject, user=pm_user)