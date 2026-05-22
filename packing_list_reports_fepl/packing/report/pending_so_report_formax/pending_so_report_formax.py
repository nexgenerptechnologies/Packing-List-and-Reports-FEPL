import frappe
from frappe import _

def execute(filters=None):
	if not frappe.db.get_single_value('Packing List Settings', 'enable_pending_so_report_formax'):
		frappe.throw(_('Pending SO Report Formax is disabled in Packing List Settings.'))
	if not filters:
		filters = {}

	columns = get_columns()
	data = get_data(filters)

	return columns, data

def get_columns():
	return [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
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

	query = f"""
		SELECT
			i.item_code AS item_code,
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

			-- Pending Purchase Orders
			COALESCE((SELECT SUM(pod.qty - COALESCE(pod.received_qty, 0))
				FROM `tabPurchase Order` po
				JOIN `tabPurchase Order Item` pod ON po.name = pod.parent
				WHERE pod.item_code = i.item_code 
				AND po.docstatus = 1 
				AND po.status NOT IN ('Closed', 'Completed')
			), 0) AS pending_po_qty,

			-- Total Stock
			COALESCE(SUM(b.actual_qty), 0) AS stock_qty,

			-- Reserved Stock
			COALESCE((SELECT SUM(sre.reserved_qty - IFNULL(sre.delivered_qty, 0))
				FROM `tabStock Reservation Entry` sre
				WHERE sre.item_code = i.item_code
				AND sre.docstatus = 1
			), 0) AS reserved_stock,

			-- Free Stock
			CASE
				WHEN COALESCE(SUM(b.actual_qty), 0) = 0 THEN 0
				ELSE GREATEST(
					COALESCE(SUM(b.actual_qty), 0) - COALESCE((SELECT SUM(sre.reserved_qty - IFNULL(sre.delivered_qty, 0))
						FROM `tabStock Reservation Entry` sre
						WHERE sre.item_code = i.item_code
						AND sre.docstatus = 1
					), 0), 0
				)
			END AS free_stock,

			-- Effective Stock
			(
				COALESCE((SELECT SUM(sre.reserved_qty - IFNULL(sre.delivered_qty, 0))
					FROM `tabStock Reservation Entry` sre
					WHERE sre.item_code = i.item_code
					AND sre.docstatus = 1
				), 0) +
				CASE
					WHEN COALESCE(SUM(b.actual_qty), 0) = 0 THEN 0
					ELSE GREATEST(
						COALESCE(SUM(b.actual_qty), 0) - COALESCE((SELECT SUM(sre.reserved_qty - IFNULL(sre.delivered_qty, 0))
							FROM `tabStock Reservation Entry` sre
							WHERE sre.item_code = i.item_code
							AND sre.docstatus = 1
						), 0), 0
					)
				END +
				COALESCE((SELECT SUM(pod.qty - COALESCE(pod.received_qty, 0))
					FROM `tabPurchase Order` po
					JOIN `tabPurchase Order Item` pod ON po.name = pod.parent
					WHERE pod.item_code = i.item_code 
					AND po.docstatus = 1 
					AND po.status NOT IN ('Closed', 'Completed')
				), 0) - 
				COALESCE((SELECT SUM(sod2.qty - COALESCE(sod2.delivered_qty, 0))
					FROM `tabSales Order` so2
					JOIN `tabSales Order Item` sod2 ON so2.name = sod2.parent
					WHERE sod2.item_code = i.item_code 
					AND so2.docstatus = 1 
					AND so2.status NOT IN ('Closed', 'Cancelled', 'Completed')
				), 0)
			) AS effective_stock_qty,

			-- Customer Ref Code
			(
				SELECT icd.ref_code
				FROM `tabItem Customer Detail` icd
				WHERE icd.parent = i.name
				AND icd.customer_name = so.customer
				LIMIT 1
			) AS cust_ref_code

		FROM `tabItem` i
		LEFT JOIN `tabBin` b ON i.item_code = b.item_code
		INNER JOIN `tabSales Order Item` sod ON i.item_code = sod.item_code
		INNER JOIN `tabSales Order` so 
			ON so.name = sod.parent 
			AND so.docstatus = 1 
			AND so.status NOT IN ('Cancelled', 'Closed', 'Completed')
		WHERE i.disabled = 0
		AND (sod.qty - IFNULL(sod.delivered_qty, 0)) > 0
		AND so.transaction_date BETWEEN %(from_date)s AND %(to_date)s
		{conditions}
		GROUP BY i.item_code, sod.name, so.name
		ORDER BY so.transaction_date ASC, so.name ASC, i.item_code ASC
	"""

	return frappe.db.sql(query, filters, as_dict=1)
