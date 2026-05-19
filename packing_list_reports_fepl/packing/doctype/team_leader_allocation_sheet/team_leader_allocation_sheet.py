# -*- coding: utf-8 -*-
# Copyright (c) 2026, Administrator and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt
import openpyxl
from io import BytesIO

class TeamLeaderAllocationSheet(Document):
	pass

@frappe.whitelist()
def fetch_partner_requests(docname):
	doc = frappe.get_doc("Team Leader Allocation Sheet", docname)
	if doc.status == "Approved":
		frappe.throw(_("Cannot fetch requests for an Approved sheet."))
		
	doc.set("items", [])
	
	selected_shipments = [s.shipment_tracker for s in doc.shipments if s.shipment_tracker]
	if not selected_shipments:
		frappe.throw(_("Please select at least one Shipment Tracker first."))
		
	# Find all individual sheets in "Pending Team Leader"
	pending_sheets = frappe.get_all("Item Allocation Sheet", 
		filters={
			"status": "Pending Team Leader",
			"docstatus": 0
		}, 
		fields=["name", "sales_partner"])
		
	matched_count = 0
	for sheet_meta in pending_sheets:
		sheet = frappe.get_doc("Item Allocation Sheet", sheet_meta["name"])
		for item in sheet.items:
			if item.shipment in selected_shipments:
				child = doc.append("items", {})
				child.shipment = item.shipment
				child.item_code = item.item_code
				child.item_name = item.item_name
				child.description = item.description
				child.total_qty = item.total_qty
				child.sales_partner = sheet.sales_partner or item.sales_partner
				child.allocation_request = item.allocation_request
				child.allocated_qty = item.allocated_qty or item.allocation_request
				child.source_doc = sheet.name
				child.source_row = item.name
				matched_count += 1
				
	doc.save()
	return f"Successfully fetched {matched_count} partner requests."

@frappe.whitelist()
def distribute_tl_quotas(docname):
	doc = frappe.get_doc("Team Leader Allocation Sheet", docname)
	if doc.status == "Approved":
		frappe.throw(_("Quotas have already been approved and distributed."))
		
	updated_docs = set()
	
	for item in doc.items:
		if item.source_doc and item.source_row:
			frappe.db.set_value("Partner Allocation Detail", item.source_row, "allocated_qty", item.allocated_qty)
			updated_docs.add(item.source_doc)
			
	for s_name in updated_docs:
		s_doc = frappe.get_doc("Item Allocation Sheet", s_name)
		s_doc.status = "Pending Partner Finalization"
		s_doc.save()
		
	doc.status = "Approved"
	doc.save()
	return "Quotas successfully approved and distributed to all Sales Partners."

@frappe.whitelist()
def download_tl_template(docname=None):
	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = "TL Quota Allocation"
	
	headers = [
		"Shipment", "Item Code", "Item Name", "Description", 
		"Shipment Qty", "Sales Partner", "Allocation Request", "TL Quota"
	]
	ws.append(headers)
	
	if docname:
		doc = frappe.get_doc("Team Leader Allocation Sheet", docname)
		for item in doc.items:
			ws.append([
				item.shipment, item.item_code, item.item_name, item.description,
				item.total_qty, item.sales_partner, item.allocation_request, item.allocated_qty or ""
			])
			
	from openpyxl.styles import Font
	for cell in ws[1]:
		cell.font = Font(bold=True)
		
	output = BytesIO()
	wb.save(output)
	output.seek(0)
	
	frappe.response['filename'] = f"TL_Quota_Allocation_{docname or 'Template'}.xlsx"
	frappe.response['filecontent'] = output.getvalue()
	frappe.response['type'] = 'binary'

@frappe.whitelist()
def upload_tl_excel(docname):
	doc = frappe.get_doc("Team Leader Allocation Sheet", docname)
	if doc.status == "Approved":
		frappe.throw(_("Cannot upload Excel data to an Approved sheet."))
		
	if not doc.excel_file:
		frappe.throw(_("Please upload an Excel file first."))
		
	file_doc = frappe.get_doc("File", {"file_url": doc.excel_file})
	file_content = file_doc.get_content()
	
	wb = openpyxl.load_workbook(BytesIO(file_content), data_only=True)
	ws = wb.active
	
	rows = list(ws.iter_rows(values_only=True))
	if not rows:
		frappe.throw(_("Excel sheet is empty."))
		
	headers = [str(h).strip().lower() for h in rows[0]]
	
	col_map = {}
	required_headers = ["shipment", "item code", "sales partner", "tl quota"]
	
	for req in required_headers:
		if req not in headers:
			frappe.throw(_("Excel template is missing required column: {0}").format(req.title()))
		col_map[req.replace(" ", "_")] = headers.index(req)
		
	def normalize_str(val):
		if val is None:
			return ""
		return str(val).strip().lower().replace(" ", "").replace("-", "")

	updated_count = 0
	for row in rows[1:]:
		shipment = str(row[col_map["shipment"]] or "").strip()
		item_code = str(row[col_map["item_code"]] or "").strip()
		sales_partner = str(row[col_map["sales_partner"]] or "").strip()
		tl_quota = flt(row[col_map["tl_quota"]])
		
		if not shipment or not item_code or not sales_partner:
			continue
			
		for child in doc.items:
			if (normalize_str(child.shipment) == normalize_str(shipment) and
				normalize_str(child.item_code) == normalize_str(item_code) and
				normalize_str(child.sales_partner) == normalize_str(sales_partner)):
				child.allocated_qty = tl_quota
				updated_count += 1
				
	doc.save()
	return f"Successfully updated {updated_count} rows from Excel."
