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
			
		# Sales Partner Upload (Draft Stage)
		if doc.status == "Draft":
			doc.set("items", [])
			for row in sheet.iter_rows(min_row=2, values_only=True):
				if not any(row): continue
				item_code = row[col_map.get("item_code")] if "item_code" in col_map else ""
				if not item_code: continue
				
				child = doc.append("items", {})
				child.item_code = str(item_code).strip()
				if "item_name" in col_map: child.item_name = str(row[col_map["item_name"]] or "").strip()
				if "description" in col_map: child.description = str(row[col_map["description"]] or "").strip()
				if "total_qty" in col_map: child.total_qty = flt(row[col_map["total_qty"]])
				if "customer" in col_map: child.customer = str(row[col_map["customer"]] or "").strip()
				if "sales_order" in col_map: child.sales_order = str(row[col_map["sales_order"]] or "").strip()
				if "allocation_request" in col_map: child.allocation_request = flt(row[col_map["allocation_request"]])
				
		# Team Leader Upload (Pending Team Leader Stage)
		elif doc.status == "Pending Team Leader":
			for row in sheet.iter_rows(min_row=2, values_only=True):
				if not any(row): continue
				item_code = str(row[col_map.get("item_code")] or "").strip()
				if not item_code: continue
				
				customer = str(row[col_map.get("customer")] or "").strip() if "customer" in col_map else ""
				sales_order = str(row[col_map.get("sales_order")] or "").strip() if "sales_order" in col_map else ""
				allocated_qty = flt(row[col_map["allocated_qty"]]) if "allocated_qty" in col_map else 0.0
				
				for child in doc.items:
					match = (child.item_code == item_code)
					if customer:
						match = match and (str(child.customer).strip() == customer)
					if sales_order:
						match = match and (str(child.sales_order).strip() == sales_order)
						
					if match:
						child.allocated_qty = allocated_qty
						
		# Sales Partner Finalization Upload (Pending Partner Finalization Stage)
		elif doc.status == "Pending Partner Finalization":
			for row in sheet.iter_rows(min_row=2, values_only=True):
				if not any(row): continue
				item_code = str(row[col_map.get("item_code")] or "").strip()
				if not item_code: continue
				
				customer = str(row[col_map.get("customer")] or "").strip() if "customer" in col_map else ""
				sales_order = str(row[col_map.get("sales_order")] or "").strip() if "sales_order" in col_map else ""
				final_allocation = flt(row[col_map["final_allocation"]]) if "final_allocation" in col_map else 0.0
				
				for child in doc.items:
					match = (child.item_code == item_code)
					if customer:
						match = match and (str(child.customer).strip() == customer)
					if sales_order:
						match = match and (str(child.sales_order).strip() == sales_order)
						
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
