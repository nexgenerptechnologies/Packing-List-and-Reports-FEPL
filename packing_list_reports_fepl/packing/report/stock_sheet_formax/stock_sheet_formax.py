import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
	if not frappe.db.get_single_value('Packing List Settings', 'enable_stock_sheet_formax'):
		frappe.throw(_('Stock Sheet Formax is disabled in Packing List Settings.'))
	if not filters:
		filters = {}

	# Ensure defensive default dates if they are missing
	filters.setdefault("from_date", "1900-01-01")
	filters.setdefault("to_date", "2100-12-31")

	columns = get_columns()
	data = get_data(filters)

	return columns, data

def get_columns():
	return [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 200},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Link", "options": "Brand", "width": 100},
		{"label": _("SPQ"), "fieldname": "spq", "fieldtype": "Float", "width": 80},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 120},
		{"label": _("Stock Qty"), "fieldname": "stock_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Reserved Stock"), "fieldname": "reserved_stock", "fieldtype": "Float", "width": 120},
		{"label": _("Free Stock"), "fieldname": "free_stock", "fieldtype": "Float", "width": 100},
		{"label": _("Pending PO Qty"), "fieldname": "pending_po_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Pending SO Qty"), "fieldname": "pending_so_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Effective Stock"), "fieldname": "effective_stock_qty", "fieldtype": "Float", "width": 120}
	]

def get_data(filters):
	conditions = ""
	if filters.get("item_code"):
		conditions += " AND i.item_code = %(item_code)s"
	if filters.get("brand"):
		conditions += " AND i.brand = %(brand)s"
	if filters.get("item_group"):
		conditions += " AND i.item_group = %(item_group)s"

	# Base query to get active items and current physical stock
	base_query = f"""
		SELECT
			i.item_code AS item_code,
			i.item_name AS item_name,
			i.description AS description,
			i.brand AS brand,
			i.custom_standard_packing_qty AS spq,
			i.item_group AS item_group,
			COALESCE(SUM(b.actual_qty), 0) AS stock_qty
		FROM `tabItem` i
		LEFT JOIN `tabBin` b ON i.item_code = b.item_code
		WHERE i.disabled = 0 {conditions}
		GROUP BY i.item_code
	"""
	
	raw_data = frappe.db.sql(base_query, filters, as_dict=1)
	if not raw_data:
		return []

	# 1. Bulk fetch Reserved Stock from Stock Reservation Entry
	reserved_data = frappe.db.sql("""
		SELECT 
			item_code, 
			SUM(reserved_qty - IFNULL(delivered_qty, 0)) AS reserved_qty
		FROM `tabStock Reservation Entry`
		WHERE docstatus = 1
		GROUP BY item_code
	""", as_dict=1)
	reserved_stock_map = {r.item_code: flt(r.reserved_qty) for r in reserved_data}

	# 2. Bulk fetch Pending PO Qty
	po_data = frappe.db.sql("""
		SELECT 
			pod.item_code, 
			SUM(pod.qty - COALESCE(pod.received_qty, 0)) AS pending_po_qty
		FROM `tabPurchase Order` po
		JOIN `tabPurchase Order Item` pod ON po.name = pod.parent
		WHERE po.docstatus = 1 
		AND po.status NOT IN ('Closed', 'Completed')
		AND po.transaction_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY pod.item_code
	""", filters, as_dict=1)
	pending_po_map = {p.item_code: flt(p.pending_po_qty) for p in po_data}

	# 3. Bulk fetch Pending SO Qty
	so_data = frappe.db.sql("""
		SELECT 
			sod.item_code, 
			SUM(sod.qty - COALESCE(sod.delivered_qty, 0)) AS pending_so_qty
		FROM `tabSales Order` so
		JOIN `tabSales Order Item` sod ON so.name = sod.parent
		WHERE so.docstatus = 1 
		AND so.status NOT IN ('Closed', 'Cancelled', 'Completed')
		AND so.transaction_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY sod.item_code
	""", filters, as_dict=1)
	pending_so_map = {s.item_code: flt(s.pending_so_qty) for s in so_data}

	# 4. Map the bulk-fetched data to the results and compute Free/Effective stock
	enriched_data = []
	for row in raw_data:
		item_code = row['item_code']
		stock_qty = flt(row['stock_qty'])
		
		res_stock = reserved_stock_map.get(item_code, 0.0)
		row['reserved_stock'] = res_stock
		
		# Free Stock calculation logic matches original CASE WHEN stock_qty = 0 THEN 0 ELSE GREATEST(...)
		free_stock = 0.0
		if stock_qty > 0:
			free_stock = max(stock_qty - res_stock, 0.0)
		row['free_stock'] = free_stock
		
		pending_po = pending_po_map.get(item_code, 0.0)
		row['pending_po_qty'] = pending_po
		
		pending_so = pending_so_map.get(item_code, 0.0)
		row['pending_so_qty'] = pending_so
		
		# Effective Stock = Reserved + Free + Pending PO - Pending SO
		row['effective_stock_qty'] = res_stock + free_stock + pending_po - pending_so
		
		enriched_data.append(row)

	return enriched_data
