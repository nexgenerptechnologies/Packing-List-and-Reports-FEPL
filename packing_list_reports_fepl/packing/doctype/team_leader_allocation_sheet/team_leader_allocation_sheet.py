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
	def validate(self):
		# Group items by item_code and verify total allocated qty does not exceed shipment qty
		items_by_code = {}
		for item in self.items:
			if not item.item_code:
				continue
			if item.item_code not in items_by_code:
				items_by_code[item.item_code] = {
					"item_name": item.item_name,
					"total_qty": flt(item.total_qty),
					"allocated_sum": 0.0
				}
			items_by_code[item.item_code]["allocated_sum"] += flt(item.allocated_qty)
			
		for code, details in items_by_code.items():
			if details["allocated_sum"] > details["total_qty"]:
				frappe.throw(
					_("For Item {0} ({1}), total allocated quota ({2}) cannot exceed Shipment Qty ({3}).")
					.format(code, details["item_name"], details["allocated_sum"], details["total_qty"])
				)

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
def get_item_spqs(docname):
	doc = frappe.get_doc("Team Leader Allocation Sheet", docname)
	item_codes = list(set([item.item_code for item in doc.items if item.item_code]))
	spqs = {}
	if item_codes:
		items_data = frappe.get_all("Item", filters={"name": ["in", item_codes]}, fields=["name", "custom_standard_packing_qty"])
		for item in items_data:
			spqs[item.name] = item.custom_standard_packing_qty or 1
	return spqs

@frappe.whitelist()
def download_tl_template(docname=None):
	if not docname:
		frappe.throw(_("No document name provided."))
		
	doc = frappe.get_doc("Team Leader Allocation Sheet", docname)
	
	items_by_code = {}
	all_partners = sorted(list(set([item.sales_partner for item in doc.items if item.sales_partner])))
	
	for item in doc.items:
		if not item.item_code:
			continue
		if item.item_code not in items_by_code:
			spq = frappe.db.get_value("Item", item.item_code, "custom_standard_packing_qty") or 1
			items_by_code[item.item_code] = {
				"item_code": item.item_code,
				"item_name": item.item_name,
				"description": item.description,
				"total_qty": item.total_qty or 0,
				"spq": spq,
				"partners": {},
				"total_req": 0,
				"total_quota": 0
			}
		
		partner_data = items_by_code[item.item_code]["partners"]
		partner_data[item.sales_partner] = {
			"request": item.allocation_request or 0,
			"quota": item.allocated_qty if item.allocated_qty is not None else item.allocation_request or 0
		}
		items_by_code[item.item_code]["total_req"] += item.allocation_request or 0
		items_by_code[item.item_code]["total_quota"] += item.allocated_qty if item.allocated_qty is not None else item.allocation_request or 0

	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = "TL Quota Allocation"
	
	headers = ["Item Code", "Item Name", "Description", "Shipment Qty", "SPQ"]
	for p in all_partners:
		headers.append(p)
	headers.extend(["Total Allocation Request", "TL Quota"])
	
	ws.append(headers)
	
	for code, details in items_by_code.items():
		row_data = [
			details["item_code"],
			details["item_name"],
			details["description"],
			details["total_qty"],
			details["spq"]
		]
		for p in all_partners:
			quota = details["partners"].get(p, {}).get("quota", 0)
			row_data.append(quota)
		row_data.append(details["total_req"])
		row_data.append(details["total_quota"])
		ws.append(row_data)
		
	from openpyxl.styles import Font, PatternFill, Alignment
	
	header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
	header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
	center_align = Alignment(horizontal="center", vertical="center")
	left_align = Alignment(horizontal="left", vertical="center")
	
	for col_idx, cell in enumerate(ws[1], 1):
		cell.font = header_font
		cell.fill = header_fill
		cell.alignment = center_align if col_idx not in [2, 3] else left_align
		
	for col in ws.columns:
		vals = [cell.value for cell in col if cell.value is not None]
		max_len = max(len(str(v)) for v in vals) if vals else 10
		col_letter = openpyxl.utils.get_column_letter(col[0].column)
		ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
		
	output = BytesIO()
	wb.save(output)
	output.seek(0)
	
	frappe.response['filename'] = f"TL_Quota_Allocation_{docname}.xlsx"
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
		
	raw_headers = [str(h).strip() for h in rows[0]]
	headers_lower = [h.lower() for h in raw_headers]
	
	if "item code" not in headers_lower:
		frappe.throw(_("Excel template is missing required column: Item Code"))
			
	item_code_idx = headers_lower.index("item code")
	
	static_cols = ["item code", "item name", "description", "shipment qty", "spq", "total allocation request", "tl quota"]
	
	partner_cols = []
	for idx, h in enumerate(raw_headers):
		h_lower = h.lower()
		if h_lower not in static_cols:
			partner_cols.append({
				"partner_name": h,
				"index": idx
			})
			
	if not partner_cols:
		frappe.throw(_("Excel sheet does not contain any Sales Partner columns."))
		
	def normalize_str(val):
		if val is None:
			return ""
		return str(val).strip().lower().replace(" ", "").replace("-", "").replace("_", "")

	updated_count = 0
	for row in rows[1:]:
		item_code = str(row[item_code_idx] or "").strip()
		if not item_code:
			continue
			
		for p_col in partner_cols:
			partner_name = p_col["partner_name"]
			val_idx = p_col["index"]
			
			val = 0
			if val_idx < len(row):
				val = flt(row[val_idx])
				
			for child in doc.items:
				if (normalize_str(child.item_code) == normalize_str(item_code) and
					normalize_str(child.sales_partner) == normalize_str(partner_name)):
					child.allocated_qty = val
					updated_count += 1
					
	doc.save()
	return f"Successfully updated {updated_count} partner quota entries from Excel."
