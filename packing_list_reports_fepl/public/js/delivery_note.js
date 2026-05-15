frappe.ui.form.on('Delivery Note', {
	refresh: function(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.items && frm.doc.items.length > 0) {
			frm.add_custom_button(__('Fetch Allocation'), function() {
				frm.events.fetch_allocation(frm);
			}, __('Actions'));
		}
	},
	fetch_allocation: function(frm) {
		let items_to_check = frm.doc.items.map(i => i.item_code);
		let sales_orders = frm.doc.items.map(i => i.against_sales_order).filter(so => so);

		if (sales_orders.length === 0) {
			frappe.msgprint(__('This Delivery Note is not linked to any Sales Order.'));
			return;
		}

		frappe.call({
			method: "packing_list_reports_fepl.packing.doctype.item_allocation_sheet.item_allocation_sheet.get_allocation_for_dn",
			args: {
				sales_orders: sales_orders,
				items: items_to_check
			},
			callback: function(r) {
				if (r.message) {
					let allocations = r.message;
					let updated = false;

					frm.doc.items.forEach(item => {
						let key = item.against_sales_order + "|" + item.item_code;
						if (allocations[key]) {
							frappe.model.set_value(item.doctype, item.name, 'qty', allocations[key]);
							updated = true;
						}
					});

					if (updated) {
						frm.refresh_field('items');
						frappe.show_alert({message: __('Quantities updated based on Allocation Sheet'), color: 'green'});
					} else {
						frappe.msgprint(__('No matching allocations found for these items/orders.'));
					}
				}
			}
		});
	}
});
