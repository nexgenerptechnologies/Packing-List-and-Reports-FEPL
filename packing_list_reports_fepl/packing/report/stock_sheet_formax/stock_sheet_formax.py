import frappe
from frappe import _

def execute(filters=None):
	if not filters:
		filters = {}

	columns = get_columns()
	data = get_data(filters)

	return columns, data

def get_columns():
	return [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 200
		},
		{
			"label": _("Description"),
			"fieldname": "description",
			"fieldtype": "Data",
			"width": 200
		},
		{
			"label": _("Brand"),
			"fieldname": "brand",
			"fieldtype": "Link",
			"options": "Brand",
			"width": 100
		},
		{
			"label": _("SPQ"),
			"fieldname": "spq",
			"fieldtype": "Float",
			"width": 80
		},
		{
			"label": _("Item Group"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 120
		},
		{
			"label": _("Stock Qty"),
			"fieldname": "stock_qty",
			"fieldtype": "Float",
			"width": 100
		},
		{
			"label": _("Reserved Stock"),
			"fieldname": "reserved_stock",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": _("Free Stock"),
			"fieldname": "free_stock",
			"fieldtype": "Float",
			"width": 100
		},
		{
			"label": _("Pending PO Qty"),
			"fieldname": "pending_po_qty",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": _("Pending SO Qty"),
			"fieldname": "pending_so_qty",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": _("Effective Stock"),
			"fieldname": "effective_stock_qty",
			"fieldtype": "Float",
			"width": 120
		}
	]

def get_data(filters):
	conditions = ""
	if filters.get("item_code"):
		conditions += " AND i.item_code = %(item_code)s"
	if filters.get("brand"):
		conditions += " AND i.brand = %(brand)s"
	if filters.get("item_group"):
		conditions += " AND i.item_group = %(item_group)s"

	query = f"""
		SELECT
			i.item_code AS item_code,
			i.item_name AS item_name,
			i.description AS description,
			i.brand AS brand,
			i.custom_standard_packing_qty AS spq,
			i.item_group AS item_group,

			-- Total Stock
			COALESCE(SUM(b.actual_qty), 0) AS stock_qty,

			-- Adjusted Reserved Stock
			COALESCE((
				SELECT SUM(sre.reserved_qty - IFNULL(sre.delivered_qty, 0))
				FROM `tabStock Reservation Entry` sre
				WHERE sre.item_code = i.item_code
				AND sre.docstatus = 1
			), 0) AS reserved_stock,

			-- Free Stock
			CASE
				WHEN COALESCE(SUM(b.actual_qty), 0) = 0 THEN 0
				ELSE GREATEST(
					COALESCE(SUM(b.actual_qty), 0) - COALESCE((
						SELECT SUM(sre.reserved_qty - IFNULL(sre.delivered_qty, 0))
						FROM `tabStock Reservation Entry` sre
						WHERE sre.item_code = i.item_code
						AND sre.docstatus = 1
					), 0), 0
				)
			END AS free_stock,

			-- Pending Purchase Orders
			COALESCE((
				SELECT SUM(pod.qty - COALESCE(pod.received_qty, 0))
				FROM `tabPurchase Order` po
				JOIN `tabPurchase Order Item` pod ON po.name = pod.parent
				WHERE pod.item_code = i.item_code 
				AND po.docstatus = 1 
				AND po.status NOT IN ('Closed', 'Completed')
				AND po.transaction_date BETWEEN %(from_date)s AND %(to_date)s
			), 0) AS pending_po_qty,

			-- Pending Sales Orders
			COALESCE((
				SELECT SUM(sod.qty - COALESCE(sod.delivered_qty, 0))
				FROM `tabSales Order` so
				JOIN `tabSales Order Item` sod ON so.name = sod.parent
				WHERE sod.item_code = i.item_code 
				AND so.docstatus = 1 
				AND so.status NOT IN ('Closed', 'Cancelled', 'Completed')
				AND so.transaction_date BETWEEN %(from_date)s AND %(to_date)s
			), 0) AS pending_so_qty,

			-- Effective Stock
			(
				COALESCE((
					SELECT SUM(sre.reserved_qty - IFNULL(sre.delivered_qty, 0))
					FROM `tabStock Reservation Entry` sre
					WHERE sre.item_code = i.item_code
					AND sre.docstatus = 1
				), 0) +
				CASE
					WHEN COALESCE(SUM(b.actual_qty), 0) = 0 THEN 0
					ELSE GREATEST(
						COALESCE(SUM(b.actual_qty), 0) - COALESCE((
							SELECT SUM(sre.reserved_qty - IFNULL(sre.delivered_qty, 0))
							FROM `tabStock Reservation Entry` sre
							WHERE sre.item_code = i.item_code
							AND sre.docstatus = 1
						), 0), 0
					)
				END +
				COALESCE((
					SELECT SUM(pod.qty - COALESCE(pod.received_qty, 0))
					FROM `tabPurchase Order` po
					JOIN `tabPurchase Order Item` pod ON po.name = pod.parent
					WHERE pod.item_code = i.item_code 
					AND po.docstatus = 1 
					AND po.status NOT IN ('Closed', 'Completed')
					AND po.transaction_date BETWEEN %(from_date)s AND %(to_date)s
				), 0) -
				COALESCE((
					SELECT SUM(sod.qty - COALESCE(sod.delivered_qty, 0))
					FROM `tabSales Order` so
					JOIN `tabSales Order Item` sod ON so.name = sod.parent
					WHERE sod.item_code = i.item_code 
					AND so.docstatus = 1 
					AND so.status NOT IN ('Closed', 'Cancelled', 'Completed')
					AND so.transaction_date BETWEEN %(from_date)s AND %(to_date)s
				), 0)
			) AS effective_stock_qty

		FROM `tabItem` i
		LEFT JOIN `tabBin` b ON i.item_code = b.item_code
		WHERE i.disabled = 0 {conditions}
		GROUP BY i.item_code
	"""

	return frappe.db.sql(query, filters, as_dict=1)
