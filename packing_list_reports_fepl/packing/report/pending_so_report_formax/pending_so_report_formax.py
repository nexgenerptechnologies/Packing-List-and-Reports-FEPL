import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
	if not frappe.db.get_single_value('Packing List Settings', 'enable_pending_so_report_formax'):
		frappe.throw(_('Pending SO Report Formax is disabled in Packing List Settings.'))
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
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
		{"label": _("CPN"), "fieldname": "custom_cpn", "fieldtype": "Data", "width": 120},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 200},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Link", "options": "Brand", "width": 100},
		{"label": _("SPQ"), "fieldname": "spq", "fieldtype": "Float", "width": 80},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 120},
		{"label": _("SO Date"), "fieldname": "so_date", "fieldtype": "Data", "width": 100},
		{"label": _("SO Number"), "fieldname": "so_number", "fieldtype": "Link", "options": "Sales Order", "width": 130},
		{"label": _("Cust PO No"), "fieldname": "customer_po_no", "fieldtype": "Data", "width": 120},
		{"label": _("Cust PO Date"), "fieldname": "customer_po_date", "fieldtype": "Data", "width": 100},
		{"label": _("Sales Partner"), "fieldname": "sales_partner", "fieldtype": "Link", "options": "Sales Partner", "width": 120},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 150},
		{"label": _("SO Qty"), "fieldname": "so_qty", "fieldtype": "Float", "width": 100},
		{"label": _("SO Price"), "fieldname": "so_price", "fieldtype": "Currency", "width": 100},
		{"label": _("Delivery Date"), "fieldname": "delivery_date", "fieldtype": "Data", "width": 100},
		{"label": _("SO Pending Qty"), "fieldname": "so_wise_pending_qty", "fieldtype": "Float", "width": 120},
		{"label": _("SO Reserved Qty"), "fieldname": "so_reserved_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Pending PO Qty"), "fieldname": "pending_po_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Stock Qty"), "fieldname": "stock_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Reserved Stock"), "fieldname": "reserved_stock", "fieldtype": "Float", "width": 120},
		{"label": _("Free Stock"), "fieldname": "free_stock", "fieldtype": "Float", "width": 100},
		{"label": _("Effective Stock"), "fieldname": "effective_stock_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Cust Ref Code"), "fieldname": "cust_ref_code", "fieldtype": "Data", "width": 120}
	]

def get_data(filters):
	conditions = ""
	if filters.get("customer"):
		conditions += " AND so.customer = %(customer)s"
	if filters.get("item_code"):
		conditions += " AND i.item_code = %(item_code)s"
	if filters.get("brand"):
		conditions += " AND i.brand = %(brand)s"
	if filters.get("sales_partner"):
		conditions += " AND so.sales_partner = %(sales_partner)s"

	base_query = f"""
		SELECT
			i.item_code AS item_code,
			sod.custom_cpn AS custom_cpn,
			i.item_name AS item_name,
			i.description AS description,
			i.brand AS brand,
			i.custom_standard_packing_qty AS spq,
			i.item_group AS item_group,

			DATE_FORMAT(so.transaction_date, '%%d-%%m-%%Y') AS so_date,
			so.name AS so_number,
			so.po_no AS customer_po_no,
			DATE_FORMAT(so.po_date, '%%d-%%m-%%Y') AS customer_po_date,
			so.sales_partner AS sales_partner,
			so.customer_name AS customer_name,
			sod.qty AS so_qty,
			sod.rate AS so_price,
			DATE_FORMAT(sod.delivery_date, '%%d-%%m-%%Y') AS delivery_date,
			(sod.qty - IFNULL(sod.delivered_qty, 0)) AS so_wise_pending_qty,
			i.name AS item_docname,
			so.customer AS customer_id
		FROM `tabItem` i
		INNER JOIN `tabSales Order Item` sod ON i.item_code = sod.item_code
		INNER JOIN `tabSales Order` so 
			ON so.name = sod.parent 
			AND so.docstatus = 1 
			AND so.status NOT IN ('Cancelled', 'Closed', 'Completed')
		WHERE i.disabled = 0
		AND (sod.qty - IFNULL(sod.delivered_qty, 0)) > 0
		AND so.transaction_date BETWEEN %(from_date)s AND %(to_date)s
		{conditions}
		ORDER BY so.transaction_date ASC, so.name ASC, i.item_code ASC
	"""

	raw_data = frappe.db.sql(base_query, filters, as_dict=1)
	if not raw_data:
		return []

	# 1. Bulk fetch Total Stock Qty per item
	bin_data = frappe.db.sql("""
		SELECT 
			item_code, 
			SUM(actual_qty) AS stock_qty
		FROM `tabBin`
		GROUP BY item_code
	""", as_dict=1)
	stock_qty_map = {b.item_code: flt(b.stock_qty) for b in bin_data}

	# 2. Bulk fetch Reserved Stock per item
	reserved_data = frappe.db.sql("""
		SELECT 
			item_code, 
			SUM(reserved_qty - IFNULL(delivered_qty, 0)) AS reserved_qty
		FROM `tabStock Reservation Entry`
		WHERE docstatus = 1
		GROUP BY item_code
	""", as_dict=1)
	reserved_stock_map = {r.item_code: flt(r.reserved_qty) for r in reserved_data}

	# 2.5 Bulk fetch SO Reserved Stock
	so_reserved_data = frappe.db.sql("""
		SELECT 
			item_code, 
			voucher_no,
			SUM(reserved_qty - IFNULL(delivered_qty, 0)) AS reserved_qty
		FROM `tabStock Reservation Entry`
		WHERE docstatus = 1 AND voucher_type = 'Sales Order'
		GROUP BY item_code, voucher_no
	""", as_dict=1)
	so_reserved_map = {(r.item_code, r.voucher_no): flt(r.reserved_qty) for r in so_reserved_data}

	# 3. Bulk fetch Pending PO Qty
	po_data = frappe.db.sql("""
		SELECT 
			pod.item_code, 
			SUM(pod.qty - COALESCE(pod.received_qty, 0)) AS pending_po_qty
		FROM `tabPurchase Order` po
		JOIN `tabPurchase Order Item` pod ON po.name = pod.parent
		WHERE po.docstatus = 1 
		AND po.status NOT IN ('Closed', 'Completed')
		GROUP BY pod.item_code
	""", as_dict=1)
	pending_po_map = {p.item_code: flt(p.pending_po_qty) for p in po_data}

	# 4. Bulk fetch Total Pending SO Qty per item
	so_pending_data = frappe.db.sql("""
		SELECT 
			sod.item_code, 
			SUM(sod.qty - COALESCE(sod.delivered_qty, 0)) AS pending_so_qty
		FROM `tabSales Order` so
		JOIN `tabSales Order Item` sod ON so.name = sod.parent
		WHERE so.docstatus = 1 
		AND so.status NOT IN ('Closed', 'Cancelled', 'Completed')
		GROUP BY sod.item_code
	""", as_dict=1)
	pending_so_map = {s.item_code: flt(s.pending_so_qty) for s in so_pending_data}

	# 5. Bulk fetch Customer Reference Codes
	ref_data = frappe.db.sql("""
		SELECT parent, customer_name, ref_code
		FROM `tabItem Customer Detail`
	""", as_dict=1)
	ref_code_map = {(r.parent, r.customer_name): r.ref_code for r in ref_data}

	# 6. Map all bulk-fetched data in Python
	enriched_data = []
	for row in raw_data:
		item_code = row['item_code']
		item_docname = row['item_docname']
		customer_id = row['customer_id']
		
		# Total Stock
		stock_qty = stock_qty_map.get(item_code, 0.0)
		row['stock_qty'] = stock_qty
		
		# Reserved Stock
		res_stock = reserved_stock_map.get(item_code, 0.0)
		row['reserved_stock'] = res_stock
		
		# SO Reserved Qty
		so_res_stock = so_reserved_map.get((item_code, row['so_number']), 0.0)
		row['so_reserved_qty'] = so_res_stock
		
		# Free Stock
		free_stock = 0.0
		if stock_qty > 0:
			free_stock = max(stock_qty - res_stock, 0.0)
		row['free_stock'] = free_stock
		
		# Pending PO Qty
		pending_po = pending_po_map.get(item_code, 0.0)
		row['pending_po_qty'] = pending_po
		
		# Total Pending SO Qty
		total_pending_so = pending_so_map.get(item_code, 0.0)
		
		# Effective Stock = Reserved + Free + Pending PO - Total Pending SO
		row['effective_stock_qty'] = res_stock + free_stock + pending_po - total_pending_so
		
		# Customer Ref Code
		row['cust_ref_code'] = ref_code_map.get((item_docname, customer_id))
		
		# Clean up temporary lookup keys
		row.pop('item_docname', None)
		row.pop('customer_id', None)
		
		enriched_data.append(row)

	return enriched_data
