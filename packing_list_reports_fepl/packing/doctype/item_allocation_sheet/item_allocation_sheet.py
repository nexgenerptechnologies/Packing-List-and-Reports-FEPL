import frappe
from frappe.model.document import Document
from frappe import _

class ItemAllocationSheet(Document):
	def onload(self):
		ensure_custom_fields()
		
	def validate(self):
		ensure_custom_fields()
		
		# Validation: Make sure Final Allocation sum does not exceed TL Quota per Item Code
		if self.status == "Pending Partner Finalization":
			item_quotas = {}
			item_finals = {}
			for item in self.items:
				item_quotas[item.item_code] = max(item_quotas.get(item.item_code, 0), item.allocated_qty or 0)
				item_finals[item.item_code] = item_finals.get(item.item_code, 0) + (item.final_allocation or 0)
				
			for item_code, final_sum in item_finals.items():
				quota = item_quotas.get(item_code, 0)
				if final_sum > quota:
					frappe.throw(_("Item {0}: Total Final Allocation ({1}) exceeds the Quota allocated by Team Leader ({2}).").format(item_code, final_sum, quota))

	def before_save(self):
		# Re-map sales partner based on user if not already set
		if not self.sales_partner:
			sp_name = None
			try:
				# Standard ERPNext mapping via Portal User child table
				sp_name = frappe.db.get_value("Portal User", {"user": frappe.session.user, "parenttype": "Sales Partner"}, "parent")
			except Exception:
				pass
				
			if not sp_name:
				try:
					# Fallback: check if Sales Partner name matches the session user email
					sp_name = frappe.db.get_value("Sales Partner", {"name": frappe.session.user}, "name")
				except Exception:
					pass
					
			if sp_name:
				self.sales_partner = sp_name
				
		# Calculate total allocation request per item code
		item_totals = {}
		for item in self.items:
			if self.sales_partner:
				item.sales_partner = self.sales_partner
			item_totals[item.item_code] = item_totals.get(item.item_code, 0) + (item.allocation_request or 0)
			
		for item in self.items:
			item.total_allocation_request = item_totals[item.item_code]

	def on_submit(self):
		self.db_set("status", "Approved")
		
		# Reserve quantities in Sales Orders
		for item in self.items:
			if item.sales_order and item.final_allocation > 0:
				# Find the Sales Order Item matching the item code
				so_item = frappe.db.get_value("Sales Order Item", {
					"parent": item.sales_order,
					"item_code": item.item_code
				}, ["name", "custom_reserved_qty"], as_dict=1)
				
				if so_item:
					current_reserved = so_item.custom_reserved_qty or 0.0
					new_reserved = current_reserved + item.final_allocation
					frappe.db.set_value("Sales Order Item", so_item.name, "custom_reserved_qty", new_reserved)
					
	def on_cancel(self):
		# Restriction: Only the owner (the Sales Partner who submitted it) or a System/Sales Manager can cancel
		is_owner = (self.owner == frappe.session.user)
		is_authorized = is_owner or ("System Manager" in frappe.get_roles() or "Sales Manager" in frappe.get_roles())
		
		if not is_authorized:
			frappe.throw(_("You are not authorized to unreserve/cancel this document. Only the submitting Sales Partner or a Team Leader can do this."))
			
		# Unreserve quantities in Sales Orders
		for item in self.items:
			if item.sales_order and item.final_allocation > 0:
				so_item = frappe.db.get_value("Sales Order Item", {
					"parent": item.sales_order,
					"item_code": item.item_code
				}, ["name", "custom_reserved_qty"], as_dict=1)
				
				if so_item:
					current_reserved = so_item.custom_reserved_qty or 0.0
					new_reserved = max(0.0, current_reserved - item.final_allocation)
					frappe.db.set_value("Sales Order Item", so_item.name, "custom_reserved_qty", new_reserved)

def ensure_custom_fields():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
	create_custom_fields({
		"Sales Order Item": [
			{
				"fieldname": "custom_reserved_qty",
				"label": "Reserved Qty from Shipment",
				"fieldtype": "Float",
				"insert_after": "delivered_qty",
				"read_only": 1
			}
		]
	})

@frappe.whitelist()
def upload_excel_data(docname):
	doc = frappe.get_doc("Item Allocation Sheet", docname)
	if doc.docstatus == 1:
		frappe.throw(_("Cannot upload Excel to a submitted document."))
		
	import openpyxl
	from frappe.utils import flt
	
	try:
		file_doc = frappe.get_doc("File", {"file_url": doc.excel_file})
		wb = openpyxl.load_workbook(file_doc.get_full_path(), data_only=True)
		sheet = wb.active
		
		header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True))
		col_map = {}
		expected = {
			"item_code": ["Item Code", "item code"],
			"item_name": ["Item Name", "item name"],
			"description": ["Description", "description"],
			"total_qty": ["Shipment Qty", "Shipment Quantity", "Qty"],
			"customer": ["Customer Name", "Customer", "customer"],
			"sales_order": ["Sales Order", "sales order"],
			"allocation_request": ["Allocation Request", "Allocation Requested", "Allocation Request Qty"],
			"allocated_qty": ["TL Quota", "Quota", "Allocated Qty", "Allocated Quantity"],
			"final_allocation": ["Final Allocation", "Final Allocated Qty"],
			"sales_partner": ["Partner Name", "Sales Partner"]
		}
		
		for idx, cell in enumerate(header_row):
			if not cell: continue
			clean = str(cell).strip().lower()
			for key, aliases in expected.items():
				if any(alias.lower() == clean for alias in aliases):
					col_map[key] = idx
					
		if "item_code" not in col_map:
			frappe.throw(_("Could not find 'Item Code' column in Excel file."))
			
		# Fetch all items in the selected shipments to strictly validate against
		shipment_items = []
		for s_row in doc.shipments:
			if s_row.shipment_tracker:
				items_in_shipment = frappe.get_all("Shipment Item", 
					filters={"parent": s_row.shipment_tracker}, 
					fields=["item_code", "item_name", "description", "qty"])
				for item in items_in_shipment:
					item["shipment_tracker"] = s_row.shipment_tracker
					shipment_items.append(item)
					
		def normalize_str(s):
			if not s: return ""
			import re
			s = str(s)
			s = re.sub(r'<[^>]*>', '', s)
			s = s.replace('\xa0', ' ').replace('\r', '').replace('\n', '')
			s = " ".join(s.split())
			return s.strip().lower()

		current_item_code = ""
		current_item_name = ""
		current_description = ""
		current_total_qty = 0.0

		# Sales Partner Upload (Draft Stage)
		if doc.status == "Draft":
			doc.set("items", [])
			excel_totals = {}
			parsed_rows = []
			row_idx = 1
			
			for row in sheet.iter_rows(min_row=2, values_only=True):
				row_idx += 1
				if not any(row): continue
				
				excel_item_code = row[col_map.get("item_code")] if "item_code" in col_map else None
				excel_item_name = row[col_map.get("item_name")] if "item_name" in col_map else None
				excel_desc = row[col_map.get("description")] if "description" in col_map else None
				excel_qty = row[col_map.get("total_qty")] if "total_qty" in col_map else None
				
				# If Item Code is specified, we update tracking context
				if excel_item_code and str(excel_item_code).strip():
					current_item_code = str(excel_item_code).strip()
					current_item_name = str(excel_item_name or "").strip()
					current_description = str(excel_desc or "").strip()
					current_total_qty = flt(excel_qty)
					
				if not current_item_code:
					continue
					
				customer = str(row[col_map.get("customer")] or "").strip() if "customer" in col_map else ""
				sales_order = str(row[col_map.get("sales_order")] or "").strip() if "sales_order" in col_map else ""
				allocation_req = flt(row[col_map["allocation_request"]]) if "allocation_request" in col_map else 0.0
				
				# 1. Strict Reconciliation: Verify against items in the selected Shipment Trackers
				matched_item = None
				for s_item in shipment_items:
					if normalize_str(s_item["item_code"]) == normalize_str(current_item_code):
						if normalize_str(s_item["item_name"]) == normalize_str(current_item_name) and \
						   normalize_str(s_item["description"]) == normalize_str(current_description):
							matched_item = s_item
							break
							
				if not matched_item:
					frappe.throw(_("Row {0}: Item '{1}' (Name: '{2}', Desc: '{3}') does not strictly match any item in the selected Shipment Trackers.").format(
						row_idx, current_item_code, current_item_name, current_description
					))
					
				excel_totals[current_item_code] = excel_totals.get(current_item_code, 0.0) + allocation_req
				
				parsed_rows.append({
					"item_code": current_item_code,
					"item_name": current_item_name,
					"description": current_description,
					"total_qty": current_total_qty,
					"customer": customer,
					"sales_order": sales_order,
					"allocation_request": allocation_req,
					"shipment": matched_item["shipment_tracker"]
				})
				
			# 2. Strict Limit Validation: Cannot exceed total Shipment Quantity
			for item_code, total_req in excel_totals.items():
				ship_qty = sum(item["qty"] for item in shipment_items if normalize_str(item["item_code"]) == normalize_str(item_code))
				if total_req > ship_qty:
					frappe.throw(_("Row {0} / Item Code '{1}': Total Allocation Request ({2}) exceeds the Shipment Quantity ({3})!").format(
						row_idx, item_code, total_req, ship_qty
					))
					
			# Append clean child rows
			for r_data in parsed_rows:
				child = doc.append("items", {})
				child.item_code = r_data["item_code"]
				child.item_name = r_data["item_name"]
				child.description = r_data["description"]
				child.total_qty = r_data["total_qty"]
				child.customer = r_data["customer"]
				child.sales_order = r_data["sales_order"]
				child.allocation_request = r_data["allocation_request"]
				child.shipment = r_data["shipment"]
				
		# Team Leader Upload (Pending Team Leader Stage)
		elif doc.status == "Pending Team Leader":
			for row in sheet.iter_rows(min_row=2, values_only=True):
				if not any(row): continue
				excel_item_code = row[col_map.get("item_code")] if "item_code" in col_map else None
				if excel_item_code and str(excel_item_code).strip():
					current_item_code = str(excel_item_code).strip()
					
				if not current_item_code:
					continue
				
				customer = str(row[col_map.get("customer")] or "").strip() if "customer" in col_map else ""
				sales_order = str(row[col_map.get("sales_order")] or "").strip() if "sales_order" in col_map else ""
				allocated_qty = flt(row[col_map["allocated_qty"]]) if "allocated_qty" in col_map else 0.0
				
				for child in doc.items:
					match = (normalize_str(child.item_code) == normalize_str(current_item_code))
					if customer:
						match = match and (normalize_str(child.customer) == normalize_str(customer))
					if sales_order:
						match = match and (normalize_str(child.sales_order) == normalize_str(sales_order))
						
					if match:
						child.allocated_qty = allocated_qty
						
		# Sales Partner Finalization Upload (Pending Partner Finalization Stage)
		elif doc.status == "Pending Partner Finalization":
			for row in sheet.iter_rows(min_row=2, values_only=True):
				if not any(row): continue
				excel_item_code = row[col_map.get("item_code")] if "item_code" in col_map else None
				if excel_item_code and str(excel_item_code).strip():
					current_item_code = str(excel_item_code).strip()
					
				if not current_item_code:
					continue
				
				customer = str(row[col_map.get("customer")] or "").strip() if "customer" in col_map else ""
				sales_order = str(row[col_map.get("sales_order")] or "").strip() if "sales_order" in col_map else ""
				final_allocation = flt(row[col_map["final_allocation"]]) if "final_allocation" in col_map else 0.0
				
				for child in doc.items:
					match = (normalize_str(child.item_code) == normalize_str(current_item_code))
					if customer:
						match = match and (normalize_str(child.customer) == normalize_str(customer))
					if sales_order:
						match = match and (normalize_str(child.sales_order) == normalize_str(sales_order))
						
					if match:
						child.final_allocation = final_allocation
						
		doc.save()
		return "Success"
	except Exception as e:
		frappe.throw(f"Failed to parse Excel: {str(e)}")

@frappe.whitelist()
def download_partner_template(docname=None):
	import openpyxl
	from io import BytesIO
	
	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = "Partner Allocation Template"
	
	headers = [
		"Item Code", "Item Name", "Description", "Shipment Qty", 
		"Customer Name", "Sales Order", "Allocation Request", "Total Allocation Request"
	]
	ws.append(headers)
	
	if docname:
		doc = frappe.get_doc("Item Allocation Sheet", docname)
		for item in doc.items:
			ws.append([
				item.item_code, item.item_name, item.description, item.total_qty,
				item.customer or "", item.sales_order or "", item.allocation_request or "", item.total_allocation_request or ""
			])
			
	from openpyxl.styles import Font
	for cell in ws[1]:
		cell.font = Font(bold=True)
		
	output = BytesIO()
	wb.save(output)
	output.seek(0)
	
	frappe.response['filename'] = "Sales_Partner_Allocation_Template.xlsx"
	frappe.response['filecontent'] = output.getvalue()
	frappe.response['type'] = 'binary'

@frappe.whitelist()
def download_team_leader_template(docname=None):
	import openpyxl
	from io import BytesIO
	
	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = "Team Lead Allocation Template"
	
	headers = [
		"Item Code", "Item Name", "Description", "Customer Name", 
		"Allocation Request", "Partner Name", "TL Quota"
	]
	ws.append(headers)
	
	if docname:
		doc = frappe.get_doc("Item Allocation Sheet", docname)
		for item in doc.items:
			ws.append([
				item.item_code, item.item_name, item.description, item.customer,
				item.allocation_request, item.sales_partner, item.allocated_qty or ""
			])
			
	from openpyxl.styles import Font
	for cell in ws[1]:
		cell.font = Font(bold=True)
		
	output = BytesIO()
	wb.save(output)
	output.seek(0)
	
	frappe.response['filename'] = "Team_Leader_Allocation_Template.xlsx"
	frappe.response['filecontent'] = output.getvalue()
	frappe.response['type'] = 'binary'

@frappe.whitelist()
def download_partner_finalization_template(docname=None):
	import openpyxl
	from io import BytesIO
	
	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = "Final Allocation Template"
	
	headers = [
		"Item Code", "Item Name", "Description", "Customer Name", 
		"Sales Order", "Allocation Request", "TL Quota", "Final Allocation"
	]
	ws.append(headers)
	
	if docname:
		doc = frappe.get_doc("Item Allocation Sheet", docname)
		for item in doc.items:
			ws.append([
				item.item_code, item.item_name, item.description, item.customer,
				item.sales_order, item.allocation_request, item.allocated_qty, item.final_allocation or ""
			])
			
	from openpyxl.styles import Font
	for cell in ws[1]:
		cell.font = Font(bold=True)
		
	output = BytesIO()
	wb.save(output)
	output.seek(0)
	
	frappe.response['filename'] = "Sales_Partner_Final_Allocation_Template.xlsx"
	frappe.response['filecontent'] = output.getvalue()
	frappe.response['type'] = 'binary'
