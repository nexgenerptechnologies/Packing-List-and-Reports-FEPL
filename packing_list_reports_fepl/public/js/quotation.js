frappe.ui.form.on("Quotation", {
	refresh: function(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Upload Customer Excel"), function() {
				new frappe.ui.FileUploader({
					as_dataurl: false,
					allow_multiple: false,
					restrictions: {
						allowed_file_types: [".xlsx", ".xls"]
					},
					on_success: function(file_doc) {
						frappe.show_alert({message: __("Processing Excel file..."), indicator: "blue"});
						frappe.call({
							method: "packing_list_reports_fepl.packing.api.upload_quotation_excel",
							args: {
								file_url: file_doc.file_url
							},
							freeze: true,
							freeze_message: __("Matching items, fetching last sale rate and stock..."),
							callback: function(r) {
								if (r.message) {
									const data = r.message;
									if (data.customer && !frm.doc.customer) {
										frm.set_value("customer", data.customer);
									}
									if (data.project) {
										frm.set_value("custom_project", data.project);
									}
									
									if (data.items && data.items.length > 0) {
										frm.clear_table("items");
										data.items.forEach(function(item) {
											let row = frm.add_child("items");
											Object.assign(row, item);
										});
										frm.refresh_field("items");
										frappe.msgprint({
											title: __("Excel Imported Successfully"),
											indicator: "green",
											message: __("Successfully loaded {0} matched items into the Quotation.").format(data.items.length)
										});
									}
									
									if (data.unmatched && data.unmatched.length > 0) {
										frappe.msgprint({
											title: __("Unmatched Items"),
											indicator: "orange",
											message: __("The following items from Excel were not found in Item Master:<br><br><b>{0}</b>").format(data.unmatched.join("<br>"))
										});
									}
								}
							}
						});
					}
				});
			}, __("Tools"));
		}
	}
});

frappe.ui.form.on("Quotation Item", {
	item_code: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.item_code) {
			// Auto fetch MSP from Item Master
			frappe.db.get_value("Item", row.item_code, "custom_msp").then(r => {
				if (r && r.message && r.message.custom_msp) {
					frappe.model.set_value(cdt, cdn, "custom_msp", r.message.custom_msp);
				}
			});
		}
	}
});