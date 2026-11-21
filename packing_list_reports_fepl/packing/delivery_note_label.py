import frappe
from frappe import _
from frappe.utils import flt, getdate, add_to_date, formatdate
import math
import json
import re

@frappe.whitelist()
def get_dn_label_items(docname):
	"""
	Returns items list with calculated label quantities for review dialog.
	"""
	doc = frappe.get_doc("Delivery Note", docname)
	
	# Fetch Customer's Purchase Order No from Delivery Note po_no
	doc_po = (doc.get("po_no") or "").strip()
	if doc_po:
		doc_po = doc_po.split("\n")[0].strip()

	# Clean Delivery Note number (strip DN- prefix e.g. DN-26-21124-1 -> 26-21124-1)
	clean_dn = re.sub(r'^DN-?', '', doc.name)

	items = []
	for item in doc.items:
		total_qty = float(item.qty or 0)
		std_val = frappe.db.get_value("Item", item.item_code, "custom_standard_packing_qty")
		std_qty = float(std_val) if std_val else total_qty
		if std_qty <= 0:
			std_qty = total_qty if total_qty > 0 else 1
			
		num_labels = int(math.ceil(total_qty / std_qty)) if std_qty > 0 else 1
		
		# Complete value from custom_cpn
		cpn_val = (item.get("custom_cpn") or "").strip()
		
		# Customer PO: item custom_customer_po or Delivery Note po_no or Sales Order po_no or extracted from CPN
		po_val = (item.get("custom_customer_po") or "").strip()
		if not po_val:
			po_val = doc_po
		if not po_val and item.get("against_sales_order"):
			po_val = (frappe.db.get_value("Sales Order", item.against_sales_order, "po_no") or "").strip()
		if not po_val and cpn_val:
			match = re.search(r'PO[-:\s#]*([A-Za-z0-9_-]+)', cpn_val, re.IGNORECASE)
			if match:
				po_val = match.group(1).strip()

		# Location directly from Item Master custom_location (fallback to item row or China)
		item_loc = frappe.db.get_value("Item", item.item_code, "custom_location")
		mfg_loc = (item_loc or item.get("custom_mfg_location") or "China").strip()
		lot_no = (item.get("custom_lot_number") or "").strip()

		items.append({
			"name": item.name,
			"item_code": item.item_code,
			"item_name": item.item_name or item.item_code,
			"custom_cpn": cpn_val,
			"custom_package_id": item.get("custom_package_id") or "",
			"custom_lot_number": lot_no,
			"custom_customer_po": po_val,
			"custom_supplier_id": "48104528",
			"custom_mfg_date": str(item.get("custom_mfg_date") or ""),
			"custom_mfg_location": mfg_loc,
			"quantity": item.qty,
			"std_qty": int(std_qty) if std_qty == int(std_qty) else std_qty,
			"num_labels": num_labels
		})
	return items

@frappe.whitelist()
def get_mat_label_html(docname, custom_quantities=None):
	"""
	Generates 50mm x 75mm automotive Mat.-Label print stream with 2D Data Matrix and 1D Code 128 barcodes.
	"""
	doc = frappe.get_doc("Delivery Note", docname)

	# Clean Delivery Note number (strip DN- prefix e.g. DN-26-21124-1 -> 26-21124-1)
	clean_dn = re.sub(r'^DN-?', '', doc.name)
	
	# Fetch Customer's Purchase Order No from Delivery Note po_no
	doc_po = (doc.get("po_no") or "").strip()
	if doc_po:
		doc_po = doc_po.split("\n")[0].strip()

	qty_map = {}
	if custom_quantities:
		if isinstance(custom_quantities, str):
			try:
				qty_map = json.loads(custom_quantities)
			except Exception:
				pass
		elif isinstance(custom_quantities, dict):
			qty_map = custom_quantities

	labels_data = []
	
	for item in doc.items:
		if item.name in qty_map:
			count = int(qty_map[item.name])
		elif item.item_code in qty_map:
			count = int(qty_map[item.item_code])
		else:
			total_qty = float(item.qty or 0)
			std_val = frappe.db.get_value("Item", item.item_code, "custom_standard_packing_qty")
			std_qty = float(std_val) if std_val else total_qty
			if std_qty <= 0:
				std_qty = total_qty if total_qty > 0 else 1
			count = int(math.ceil(total_qty / std_qty)) if std_qty > 0 else 1

		if count <= 0:
			continue

		total_qty = float(item.qty or 0)
		std_val = frappe.db.get_value("Item", item.item_code, "custom_standard_packing_qty")
		std_qty = float(std_val) if std_val else total_qty
		if std_qty <= 0:
			std_qty = total_qty if total_qty > 0 else 1
			
		std_qty_val = int(std_qty) if std_qty == int(std_qty) else std_qty

		# 1. Part No: Complete value from custom_cpn
		cpn = (item.get("custom_cpn") or "").strip()

		# 2. Purchase Order: Customer's Purchase Order No from Delivery Note (doc.po_no) or item field or extracted from CPN
		cust_po = (item.get("custom_customer_po") or "").strip()
		if not cust_po:
			cust_po = doc_po
		if not cust_po and item.get("against_sales_order"):
			cust_po = (frappe.db.get_value("Sales Order", item.against_sales_order, "po_no") or "").strip()
		if not cust_po and cpn:
			match = re.search(r'PO[-:\s#]*([A-Za-z0-9_-]+)', cpn, re.IGNORECASE)
			if match:
				cust_po = match.group(1).strip()

		# 3. Supplier ID: Fixed to 48104528 for all labels as requested
		supp_id = "48104528"

		# 4. Location: Fetched directly from Item Master custom_location (fallback to item row or China)
		item_loc = frappe.db.get_value("Item", item.item_code, "custom_location")
		mfg_loc = (item_loc or item.get("custom_mfg_location") or "China").strip()

		# 5. Lot Number: Fetched from Delivery Note Item custom_lot_number (blank if not filled)
		lot_no = (item.get("custom_lot_number") or "").strip()
		pkg_id = (item.get("custom_package_id") or "").strip()
		mfg_date_raw = item.get("custom_mfg_date") or doc.posting_date
		
		# Format dates (DD.MM.YYYY for visual display, YYYYMMDD for 2D Data Matrix Barcode)
		mfg_date_str = ""
		exp_date_str = ""
		mfg_date_dmc = ""
		exp_date_dmc = ""
		if mfg_date_raw:
			try:
				parsed_mfg = getdate(mfg_date_raw)
				mfg_date_str = parsed_mfg.strftime("%d.%m.%Y")
				mfg_date_dmc = parsed_mfg.strftime("%Y%m%d")
				parsed_exp = add_to_date(parsed_mfg, years=2)
				exp_date_str = parsed_exp.strftime("%d.%m.%Y")
				exp_date_dmc = parsed_exp.strftime("%Y%m%d")
			except Exception:
				mfg_date_str = str(mfg_date_raw)
				exp_date_str = ""

		item_desc = (item.description or "").strip()
		item_desc_clean = re.sub(r"<[^>]+>", "", item_desc).strip()
		item_name_clean = (item.item_name or item.item_code or "").strip()

		for idx in range(count):
			if idx + 1 < count:
				lbl_qty = std_qty_val
			else:
				remainder = total_qty - (std_qty_val * idx)
				lbl_qty = int(remainder) if remainder == int(remainder) else remainder
				if lbl_qty <= 0:
					lbl_qty = std_qty_val

			current_pkg_id = pkg_id
			pu_no = current_pkg_id

			# Formatted 1D Barcode Strings
			part_supp_bc = f"P{cpn}@V{supp_id}"
			pkg_qty_bc = f"{lot_no}H{current_pkg_id}@Q{lbl_qty:05d}" if isinstance(lbl_qty, int) else f"{lot_no}H{current_pkg_id}@Q{lbl_qty}"

			# 2D Data Matrix Code string matching Hella MAT Label Working Excel Column B
			dmc_str = (
				f"[)>@06@12S0002"
				f"@P{cpn}"
				f"@1P{item_desc_clean}"
				f"@31P{cpn}"
				f"@12V1571"
				f"@10V{mfg_loc}"
				f"@2P0@20P"
				f"@6D{mfg_date_dmc}"
				f"@14D{exp_date_dmc}"
				f"@30PY@Z1"
				f"@K{cust_po}"
				f"@16K{clean_dn}"
				f"@V{supp_id}"
				f"@3SS{lot_no}"
				f"@Q{lbl_qty}NAR000"
				f"@20T1"
				f"@1T{lot_no}"
				f"@2T@1Z@@"
			)

			labels_data.append({
				"cpn": cpn,
				"quantity": lbl_qty,
				"mfg_location": mfg_loc,
				"supplier_name": "Formax Electronics Pvt Ltd",
				"package_id": current_pkg_id,
				"lot_number": lot_no,
				"pu_no": pu_no,
				"part_desc": item_name_clean,
				"supplier_id": supp_id,
				"customer_po": cust_po,
				"mpn": item_desc_clean,
				"ms_level": item.get("custom_ms_level") or "1",
				"mfg_date": mfg_date_str,
				"exp_date": exp_date_str,
				"shipping_note": clean_dn,
				"rohs_conf": "RoHSConf",
				"part_supp_bc": part_supp_bc,
				"pkg_qty_bc": pkg_qty_bc,
				"dmc_str": dmc_str
			})

	# Generate HTML document
	labels_json = json.dumps(labels_data)

	html = f"""<!DOCTYPE html>
<html>
<head>
	<meta charset="utf-8">
	<title>Mat.-Label (50x75mm) - {doc.name}</title>
	<style>
		@page {{
			size: 75mm 50mm;
			margin: 0mm;
		}}
		* {{
			box-sizing: border-box;
			margin: 0;
			padding: 0;
		}}
		body {{
			font-family: Arial, Helvetica, sans-serif;
			background: #fff;
			margin: 0;
			padding: 0;
			-webkit-print-color-adjust: exact;
			print-color-adjust: exact;
		}}
		.mat-label {{
			width: 75mm;
			height: 50mm;
			page-break-after: always;
			break-after: page;
			page-break-inside: avoid;
			box-sizing: border-box;
			padding: 2.0mm 3.0mm 1.5mm 3.0mm;
			position: relative;
			background: #fff;
			overflow: hidden;
			display: flex;
			flex-direction: column;
			justify-content: space-between;
		}}
		/* Top section - Height 18.5mm with 18.2mm DMC + Quiet Zone */
		.top-section {{
			display: flex;
			flex-direction: row;
			align-items: center;
			height: 18.5mm;
			overflow: hidden;
		}}
		.dmc-container {{
			width: 18.2mm;
			height: 18.2mm;
			margin-right: 2.5mm;
			flex-shrink: 0;
			display: flex;
			align-items: center;
			justify-content: center;
			background: #ffffff;
		}}
		.dmc-canvas {{
			width: 18.2mm;
			height: 18.2mm;
			image-rendering: -webkit-optimize-contrast;
			image-rendering: pixelated;
			image-rendering: crisp-edges;
		}}
		.top-text-col {{
			flex: 1;
			font-size: 6.8pt;
			line-height: 1.25;
			color: #000;
			overflow: hidden;
		}}
		.top-text-col div {{
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}}
		.bold-val {{
			font-weight: bold;
			font-size: 7.8pt;
		}}

		/* Middle section - Height 14.5mm with balanced spacing */
		.mid-section {{
			display: flex;
			flex-direction: row;
			justify-content: space-between;
			height: 14.5mm;
			font-size: 6.0pt;
			line-height: 1.22;
			overflow: hidden;
			border-top: 0.5px solid #bbb;
			padding-top: 0.6mm;
		}}
		.mid-left {{
			width: 43mm;
			overflow: hidden;
		}}
		.mid-left div {{
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}}
		.mid-right {{
			width: 25.5mm;
			overflow: hidden;
		}}
		.mid-right div {{
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}}
		.pu-barcode-canvas {{
			width: 24mm;
			height: 3.0mm;
			display: block;
			image-rendering: pixelated;
			margin: 0.2mm 0;
		}}

		/* Bottom section - Height 13.5mm with balanced margins */
		.bottom-section {{
			height: 13.5mm;
			display: flex;
			flex-direction: column;
			justify-content: flex-end;
			overflow: hidden;
			border-top: 0.5px solid #bbb;
			padding-top: 0.5mm;
		}}
		.barcode-block {{
			margin-bottom: 0.2mm;
			text-align: center;
		}}
		.full-barcode-canvas {{
			width: 67mm;
			height: 3.8mm;
			display: block;
			margin: 0 auto;
			image-rendering: pixelated;
		}}
		.barcode-caption {{
			font-size: 5.6pt;
			font-family: monospace;
			font-weight: bold;
			text-align: center;
			letter-spacing: 0.2px;
		}}

		@media print {{
			.no-print {{
				display: none !important;
			}}
			html, body {{
				width: 75mm !important;
				height: auto !important;
				margin: 0 !important;
				padding: 0 !important;
				overflow: visible !important;
			}}
			.mat-label {{
				width: 75mm !important;
				height: 50mm !important;
				page-break-after: always !important;
				page-break-inside: avoid !important;
				break-after: page !important;
			}}
		}}

		@media screen {{
			body {{
				background: #e4e7eb;
				padding: 20px;
				display: flex;
				flex-direction: column;
				align-items: center;
			}}
			.no-print-toolbar {{
				background: #1f272e;
				color: #fff;
				padding: 12px 24px;
				border-radius: 8px;
				margin-bottom: 20px;
				display: flex;
				align-items: center;
				gap: 15px;
				box-shadow: 0 4px 12px rgba(0,0,0,0.15);
				font-size: 13px;
			}}
			.btn-action {{
				background: #2490ef;
				color: #fff;
				border: none;
				padding: 7px 18px;
				border-radius: 4px;
				cursor: pointer;
				font-weight: bold;
				font-size: 13px;
			}}
			.btn-action:hover {{
				background: #1976d2;
			}}
			.mat-label {{
				background: #fff;
				border: 1px dashed #aaa;
				margin-bottom: 12px;
				box-shadow: 0 2px 6px rgba(0,0,0,0.1);
			}}
		}}
	</style>
	<script src="/assets/packing_list_reports_fepl/js/bwip-js-min.js"></script>
	<script>
		if (typeof bwipjs === "undefined") {{
			document.write("<script src='https://cdn.jsdelivr.net/npm/bwip-js@3.0.4/dist/bwip-js-min.js'><\\/script>");
		}}
	</script>
</head>
<body>
	<div class="no-print no-print-toolbar">
		<div>
			<b>TSC TTP-244 Pro Tips:</b> Paper Size: <b>75mm x 50mm</b>, <b>Layout: Portrait</b>, <b>Margins: None</b>.<br>
			<b>Printer Driver:</b> Set Print Speed to <b>2.0 ips</b> (or 2.5 ips) and Darkness/Density to <b>8 - 10</b> for optimal 2D barcode scanning.
		</div>
		<button class="btn-action" onclick="window.print()">Print Labels</button>
	</div>

	<div id="labels-container"></div>

	<script>
		const labels = {labels_json};
		const container = document.getElementById("labels-container");

		labels.forEach((lbl, i) => {{
			const labelDiv = document.createElement("div");
			labelDiv.className = "mat-label";
			labelDiv.innerHTML = `
				<!-- Top Section -->
				<div class="top-section">
					<div class="dmc-container">
						<canvas id="dmc_${{i}}" class="dmc-canvas"></canvas>
					</div>
					<div class="top-text-col">
						<div><b>Part No:</b> <span class="bold-val">${{lbl.cpn}}</span></div>
						<div><b>Quantity:</b> <span class="bold-val">${{lbl.quantity}}</span></div>
						<div><b>Man. Loc:</b> ${{lbl.mfg_location}}</div>
						<div><b>Supplier:</b> ${{lbl.supplier_name}}</div>
						<div><b>Package-ID:</b> <span class="bold-val">${{lbl.package_id}}</span></div>
					</div>
				</div>

				<!-- Middle Section -->
				<div class="mid-section">
					<div class="mid-left">
						<div style="font-size: 5.0pt;"><b>Part-Desc:</b> ${{lbl.part_desc}}</div>
						<div><b>Purchase Order:</b> ${{lbl.customer_po}}</div>
						<div style="font-size: 5.6pt;"><b>Man. Part No:</b> ${{lbl.mpn}}</div>
						<div><b>MS-Level:</b> ${{lbl.ms_level}} &nbsp;&nbsp; <b>Date of Man.:</b> ${{lbl.mfg_date}}</div>
						<div style="font-size: 5.8pt;"><b>Lot number:</b> <span class="bold-val">${{lbl.lot_number || ''}}</span></div>
					</div>
					<div class="mid-right">
						<div><b>Supplier-ID:</b> ${{lbl.supplier_id}}</div>
						<div><b>PU-No.:</b> ${{lbl.pu_no}} &nbsp; <b>${{lbl.rohs_conf}}</b></div>
						<div style="font-size: 5.3pt;"><b>Shipping Note:</b> ${{lbl.shipping_note}}</div>
						<div><canvas id="pubc_${{i}}" class="pu-barcode-canvas" style="${{lbl.pu_no ? '' : 'display:none;'}}"></canvas><b>Exp.-Date:</b> ${{lbl.exp_date}}</div>
					</div>
				</div>

				<!-- Bottom Section: 1D Barcodes -->
				<div class="bottom-section">
					<div class="barcode-block">
						<canvas id="bc1_${{i}}" class="full-barcode-canvas"></canvas>
						<div class="barcode-caption">${{lbl.part_supp_bc}}</div>
					</div>
					<div class="barcode-block">
						<canvas id="bc2_${{i}}" class="full-barcode-canvas"></canvas>
						<div class="barcode-caption">${{lbl.pkg_qty_bc}}</div>
					</div>
				</div>
			`;
			container.appendChild(labelDiv);
		}});

		// Render Barcodes after DOM is attached
		window.addEventListener("DOMContentLoaded", () => {{
			renderAllBarcodes();
		}});

		function renderAllBarcodes() {{
			labels.forEach((lbl, i) => {{
				try {{
					// 1. Data Matrix Code (DMC) with Quiet Zone & Crisp 4x Rendering
					bwipjs.toCanvas(`dmc_${{i}}`, {{
						bcid: "datamatrix",
						text: lbl.dmc_str,
						scale: 4,
						padding: 2,
						backgroundcolor: "ffffff",
						includetext: false
					}});

					// 2. PU-No 1D Barcode
					if (lbl.pu_no) {{
						bwipjs.toCanvas(`pubc_${{i}}`, {{
							bcid: "code128",
							text: lbl.pu_no,
							scale: 2,
							height: 5,
							includetext: false
						}});
					}}

					// 3. Part No + Supplier ID 1D Barcode
					bwipjs.toCanvas(`bc1_${{i}}`, {{
						bcid: "code128",
						text: lbl.part_supp_bc,
						scale: 2,
						height: 5,
						includetext: false
					}});

					// 4. Package ID + Quantity 1D Barcode
					bwipjs.toCanvas(`bc2_${{i}}`, {{
						bcid: "code128",
						text: lbl.pkg_qty_bc,
						scale: 2,
						height: 5,
						includetext: false
					}});
				}} catch (err) {{
					console.error("Barcode generation error row " + i, err);
				}}
			}});

			// Auto trigger print after render
			setTimeout(() => {{
				window.print();
			}}, 500);
		}}
	</script>
</body>
</html>"""
	return html