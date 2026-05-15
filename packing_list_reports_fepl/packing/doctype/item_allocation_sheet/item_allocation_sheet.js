frappe.ui.form.on('Item Allocation Sheet', {
	item_code: function(frm) {
		if (frm.doc.item_code) {
			frappe.db.get_value('Item', frm.doc.item_code, 'item_name', (r) => {
				if (r) frm.set_value('item_name', r.item_name);
			});
			frm.trigger('update_stock');
		}
	},
	warehouse: function(frm) {
		frm.trigger('update_stock');
	},
	refresh: function(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.item_code) {
			frm.add_custom_button(__('Fetch Pending Orders'), function() {
				frm.events.fetch_pending_orders(frm);
			});
		}
	},
	fetch_pending_orders: function(frm) {
		if (!frm.doc.item_code) {
			frappe.msgprint(__('Please select an Item Code first.'));
			return;
		}

		frappe.call({
			method: "get_pending_sales_orders",
			doc: frm.doc,
			args: {
				item_code: frm.doc.item_code
			},
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					frm.clear_table('allocations');
					r.message.forEach(row => {
						let child = frm.add_child('allocations');
						child.sales_order = row.sales_order;
						child.sales_order_item = row.sales_order_item;
						child.customer = row.customer;
						child.sales_partner = row.sales_partner;
						// Optionally set allocated_qty to pending_qty or leave at 0
						child.allocated_qty = 0; 
					});
					frm.refresh_field('allocations');
					frappe.show_alert({message: __('Fetched {0} Pending Orders', [r.message.length]), color: 'blue'});
				} else {
					frappe.msgprint(__('No pending Sales Orders found for this item.'));
				}
			}
		});
	},
	update_stock: function(frm) {
		if (frm.doc.item_code && frm.doc.warehouse) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Bin",
					filters: { item_code: frm.doc.item_code, warehouse: frm.doc.warehouse },
					fieldname: "actual_qty"
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('total_available_stock', r.message.actual_qty);
					} else {
						frm.set_value('total_available_stock', 0);
					}
				}
			});
		}
	}
});

frappe.ui.form.on('Allocation Detail', {
	sales_order: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.sales_order && frm.doc.item_code) {
			// 1. Get the Sales Order Item ID
			frappe.db.get_value('Sales Order Item', 
				{ parent: row.sales_order, item_code: frm.doc.item_code }, 
				'name', 
				(r) => {
					if (r && r.name) {
						frappe.model.set_value(cdt, cdn, 'sales_order_item', r.name);
						
						// 2. Get Customer and Partner from Parent Sales Order
						frappe.db.get_value('Sales Order', row.sales_order, ['customer_name', 'sales_partner'], (parent_res) => {
							if (parent_res) {
								frappe.model.set_value(cdt, cdn, 'customer', parent_res.customer_name);
								frappe.model.set_value(cdt, cdn, 'sales_partner', parent_res.sales_partner);
							}
						});
					} else {
						frappe.msgprint(__('Item {0} not found in Sales Order {1}', [frm.doc.item_code, row.sales_order]));
						frappe.model.set_value(cdt, cdn, 'sales_order', '');
					}
				}
			);
		}
	}
});
