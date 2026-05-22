import frappe
from frappe.model.document import Document

class PackingListSettings(Document):
	pass

def update_po_line_numbers(doc, method=None):
	if not frappe.db.get_single_value('Packing List Settings', 'enable_po_line_numbering'):
		return

	import re
	name = doc.name
	if not name:
		return

	segments = re.split(r'[^a-zA-Z0-9]', name)
	numeric_segments = [s for s in segments if s.isdigit()]
	if numeric_segments:
		po_seq = numeric_segments[-1]
	else:
		po_seq = name

	meta = frappe.get_meta('Purchase Order Item')
	fields_to_update = []
	if meta.has_field('line_number'):
		fields_to_update.append('line_number')
	if meta.has_field('custom_line_number'):
		fields_to_update.append('custom_line_number')

	if not fields_to_update:
		return

	for item in doc.items:
		for field in fields_to_update:
			current_val = item.get(field)
			if not current_val or not str(current_val).strip():
				item.set(field, f'{po_seq}-{item.idx}')
