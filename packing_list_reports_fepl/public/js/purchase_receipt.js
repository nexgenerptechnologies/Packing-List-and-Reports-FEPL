frappe.ui.form.on('Purchase Receipt', {
	refresh: function(frm) {
		// Only add custom button if document is in draft state
		if (frm.doc.docstatus === 0) {
			// Check if Get Specific Items feature is enabled in Packing List Settings
			frappe.db.get_single_value('Packing List Settings', 'enable_get_specific_items')
				.then(enabled => {
					if (enabled) {
						frm.add_custom_button(__('Get Specific Items'), function() {
							// Supplier selection is mandatory
							if (!frm.doc.supplier) {
								frappe.msgprint({
									title: __('Supplier Selection Required'),
									indicator: 'red',
									message: __('Please select a Supplier first before fetching items.')
								});
								return;
							}

							// Create and display dialog
							let dialog = new frappe.ui.Dialog({
								title: __('Select Items from Purchase Order'),
								fields: [
									{
										fieldname: 'purchase_order',
										label: __('Purchase Order'),
										fieldtype: 'Link',
										options: 'Purchase Order',
										reqd: 1,
										get_query: () => {
											return {
												filters: {
													'docstatus': 1,
													'status': ['not in', ['Closed', 'Completed']],
													'supplier': frm.doc.supplier
												}
											};
										},
										onchange: function() {
											let purchase_order = dialog.get_value('purchase_order');
											if (purchase_order) {
												frappe.call({
													method: 'packing_list_reports_fepl.packing.doctype.packing_list_settings.packing_list_settings.get_po_items',
													args: {
														purchase_order: purchase_order
													},
													callback: function(r) {
														if (r.message) {
															dialog.fields_dict.items_grid.df.data = r.message;
															dialog.fields_dict.items_grid.refresh();
														}
													}
												});
											} else {
												dialog.fields_dict.items_grid.df.data = [];
												dialog.fields_dict.items_grid.refresh();
											}
										}
									},
									{
										fieldname: 'items_grid',
										label: __('Items'),
										fieldtype: 'Table',
										cannot_add_rows: true,
										cannot_delete_rows: true,
										in_place_edit: false,
										data: [],
										fields: [
											{
												fieldname: 'item_code',
												label: __('Item Code'),
												fieldtype: 'Read Only',
												in_list_view: 1,
												columns: 2
											},
											{
												fieldname: 'item_name',
												label: __('Item Name'),
												fieldtype: 'Read Only',
												in_list_view: 1,
												columns: 2
											},
											{
												fieldname: 'description',
												label: __('Description'),
												fieldtype: 'Read Only',
												in_list_view: 1,
												columns: 3
											},
											{
												fieldname: 'qty',
												label: __('Quantity'),
												fieldtype: 'Float',
												in_list_view: 1,
												columns: 1
											},
											{
												fieldname: 'uom',
												label: __('UOM'),
												fieldtype: 'Read Only',
												in_list_view: 1,
												columns: 1
											},
											{
												fieldname: 'line_number',
												label: __('Line Number'),
												fieldtype: 'Read Only',
												in_list_view: 1,
												columns: 2
											}
										]
									}
								],
								primary_action_label: __('Add Items'),
								primary_action: function(values) {
									if (!values.purchase_order) {
										frappe.msgprint(__('Please select a Purchase Order.'));
										return;
									}

									let selected_items = dialog.fields_dict.items_grid.df.data.filter(item => item.__checked);
									if (!selected_items.length) {
										frappe.msgprint(__('Please select at least one item.'));
										return;
									}

									// Clean up the first empty row if it is blank to prevent an unwanted empty first row
									let items = frm.doc.items || [];
									if (items.length === 1 && !items[0].item_code) {
										frm.clear_table('items');
									}

									// Add selected items to the Purchase Receipt items grid
									selected_items.forEach(item => {
										let row = frm.add_child('items');
										row.item_code = item.item_code;
										row.item_name = item.item_name;
										row.description = item.description;
										row.qty = item.qty;
										row.uom = item.uom;
										row.warehouse = item.warehouse;
										row.rate = item.rate;
										row.purchase_order = values.purchase_order;
										row.purchase_order_item = item.name;
										
										// Safely copy PO line number to both live and demo fields if it exists
										if (item.line_number) {
											row.line_number = item.line_number;
											row.custom_line_number = item.line_number;
										}
									});

									// Refresh fields to update UI rendering
									frm.refresh_field('items');
									frm.refresh();
									dialog.hide();
								}
							});

							dialog.show();
						}, __('Get Items From'));
					}
				});
		}
	}
});