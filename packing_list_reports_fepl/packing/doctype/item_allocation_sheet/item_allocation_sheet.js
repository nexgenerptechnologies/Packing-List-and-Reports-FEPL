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
