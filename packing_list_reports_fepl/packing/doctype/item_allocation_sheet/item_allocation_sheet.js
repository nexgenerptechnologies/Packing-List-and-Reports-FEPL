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
			// Fetch SO Item details
			frappe.db.get_value('Sales Order Item', 
				{ parent: row.sales_order, item_code: frm.doc.item_code }, 
				['name', 'customer_name', 'sales_partner'], 
				(r) => {
					if (r) {
						frappe.model.set_value(cdt, cdn, 'sales_order_item', r.name);
						frappe.model.set_value(cdt, cdn, 'customer', r.customer_name);
						frappe.model.set_value(cdt, cdn, 'sales_partner', r.sales_partner);
					} else {
						frappe.msgprint(__('Item {0} not found in Sales Order {1}', [frm.doc.item_code, row.sales_order]));
						frappe.model.set_value(cdt, cdn, 'sales_order', '');
					}
				}
			);
		}
	}
});
