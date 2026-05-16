frappe.ui.form.on('Partner Sub Allocation', {
	item_allocation_sheet: function(frm) {
		if (frm.doc.item_allocation_sheet) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Partner Allocation Detail",
					filters: { 
						parent: frm.doc.item_allocation_sheet,
						sales_partner: frm.doc.sales_partner 
					},
					fieldname: "allocated_qty"
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('quota', r.message.allocated_qty);
					}
				}
			});

			frappe.db.get_value('Item Allocation Sheet', frm.doc.item_allocation_sheet, ['item_code', 'warehouse'], (r) => {
				if (r) {
					frm.set_value('item_code', r.item_code);
					frm.set_value('warehouse', r.warehouse);
				}
			});
		}
	},
	refresh: function(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.item_code) {
			frm.add_custom_button(__('Fetch My Pending Orders'), function() {
				frm.events.fetch_pending_orders(frm);
			});
		}
	},
	fetch_pending_orders: function(frm) {
		frappe.call({
			method: "packing_list_reports_fepl.packing.doctype.item_allocation_sheet.item_allocation_sheet.get_pending_sales_orders",
			args: {
				item_code: frm.doc.item_code
			},
			callback: function(r) {
				if (r.message) {
					// Filter for this partner only
					let my_orders = r.message.filter(o => o.sales_partner === frm.doc.sales_partner);
					
					if (my_orders.length > 0) {
						frm.clear_table('sub_allocations');
						my_orders.forEach(row => {
							let child = frm.add_child('sub_allocations');
							child.sales_order = row.sales_order;
							child.sales_order_item = row.sales_order_item;
							child.customer = row.customer;
							child.allocated_qty = 0;
						});
						frm.refresh_field('sub_allocations');
					} else {
						frappe.msgprint(__('No pending orders found for you for this item.'));
					}
				}
			}
		});
	}
});

frappe.ui.form.on('Sub Allocation Detail', {
	sales_order: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.sales_order && frm.doc.item_code) {
			frappe.db.get_value('Sales Order Item', 
				{ parent: row.sales_order, item_code: frm.doc.item_code }, 
				'name', 
				(r) => {
					if (r) {
						frappe.model.set_value(cdt, cdn, 'sales_order_item', r.name);
						frappe.db.get_value('Sales Order', row.sales_order, 'customer_name', (p) => {
							if (p) frappe.model.set_value(cdt, cdn, 'customer', p.customer_name);
						});
					}
				}
			);
		}
	}
});
