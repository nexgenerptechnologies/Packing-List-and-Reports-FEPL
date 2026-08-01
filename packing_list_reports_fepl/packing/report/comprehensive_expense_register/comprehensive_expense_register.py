import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
	if not filters:
		filters = {}

	if not filters.get("company"):
		filters["company"] = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value('Global Defaults', 'default_company')

	# Ensure defensive default dates
	filters.setdefault("from_date", "1900-01-01")
	filters.setdefault("to_date", "2100-12-31")

	columns = get_columns(filters)
	data = get_data(filters)
	
	# Dynamically add account columns based on the data found
	account_columns = build_account_columns(data)
	columns.extend(account_columns)
	
	return columns, data

def get_columns(filters):
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 120},
		{"label": _("Vch No."), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 140},
		{"label": _("Particulars"), "fieldname": "particulars", "fieldtype": "Data", "width": 250},
		{"label": _("Total Gross Value"), "fieldname": "total_gross_value", "fieldtype": "Currency", "width": 140}
	]

def get_data(filters):
	conditions = get_conditions(filters)
	
	# Fetch all GL entries for the date range
	gl_entries = frappe.db.sql("""
		SELECT 
			posting_date, voucher_type, voucher_no, account, party_type, party, 
			debit, credit, against_voucher, remarks
		FROM `tabGL Entry`
		WHERE is_cancelled = 0 {conditions}
		ORDER BY posting_date ASC, voucher_no ASC
	""".format(conditions=conditions), filters, as_dict=1)

	if not gl_entries:
		return []

	# Group by voucher
	vouchers = {}
	for gle in gl_entries:
		key = (gle.voucher_type, gle.voucher_no)
		if key not in vouchers:
			vouchers[key] = []
		vouchers[key].append(gle)

	data = []
	for key, entries in vouchers.items():
		v_type, v_no = key
		
		# Identify the primary party/credit account and total gross value
		party_name = ""
		total_gross_value = 0.0
		posting_date = entries[0].posting_date
		
		# Look for actual party first
		for gle in entries:
			if gle.party:
				party_name = gle.party
				break
				
		# If no party, find the main credited account (e.g. Bank or Cash)
		if not party_name:
			credits = [e for e in entries if e.credit > 0]
			if credits:
				# Sort by highest credit to guess the main account
				credits.sort(key=lambda x: x.credit, reverse=True)
				party_name = credits[0].account
				
		# Calculate total gross value (Total Credit of the voucher)
		total_gross_value = sum(e.credit for e in entries)
		
		# We want to ignore the primary party account from the dynamic columns so we don't double count
		# But a voucher might have multiple party entries. 
		# Let's collect the Net (Debit - Credit) for all accounts.
		account_amounts = {}
		for gle in entries:
			# If this is the exact party or account we identified as the source, skip it for the breakdown
			if gle.party and gle.party == party_name:
				continue
			if not gle.party and gle.account == party_name:
				continue
				
			net_amount = flt(gle.debit) - flt(gle.credit)
			if net_amount != 0:
				account_amounts[gle.account] = account_amounts.get(gle.account, 0.0) + net_amount

		# Format Particulars exactly like Tally (Party Name \n Voucher No / Bill No)
		bill_no = entries[0].against_voucher or v_no
		particulars = f"{party_name}\n{bill_no}"

		row = {
			"posting_date": posting_date,
			"voucher_type": v_type,
			"voucher_no": v_no,
			"particulars": particulars,
			"total_gross_value": total_gross_value,
		}
		
		# Merge the dynamic account amounts into the row dictionary
		for acc, amt in account_amounts.items():
			# Replace spaces and special chars to make a safe fieldname
			safe_acc = get_safe_fieldname(acc)
			row[safe_acc] = amt
			
		data.append(row)

	return data

def get_conditions(filters):
	conditions = ""
	if filters.get("company"):
		conditions += " AND company = %(company)s"
	if filters.get("from_date"):
		conditions += " AND posting_date >= %(from_date)s"
	if filters.get("to_date"):
		conditions += " AND posting_date <= %(to_date)s"
	if filters.get("voucher_type"):
		conditions += " AND voucher_type = %(voucher_type)s"
	if filters.get("party_type"):
		conditions += " AND party_type = %(party_type)s"
	if filters.get("party"):
		conditions += " AND party = %(party)s"
	if filters.get("account"):
		conditions += " AND voucher_no IN (SELECT voucher_no FROM `tabGL Entry` WHERE account = %(account)s)"
	return conditions

def build_account_columns(data):
	# Scan all data rows to find dynamic account columns
	dynamic_fields = set()
	for row in data:
		for key in row.keys():
			if key not in ["posting_date", "voucher_type", "voucher_no", "particulars", "total_gross_value"]:
				dynamic_fields.add(key)
				
	# Sort them alphabetically (or could sort by expense group)
	dynamic_fields = sorted(list(dynamic_fields))
	
	columns = []
	for field in dynamic_fields:
		# Extract original account name from the safe fieldname. 
		# Actually, it's easier to just use the safe fieldname for both, but the label should look nice.
		label = field.replace("___", " & ").replace("__", " ").upper()
		columns.append({
			"label": label,
			"fieldname": field,
			"fieldtype": "Currency",
			"width": 140
		})
		
	return columns

def get_safe_fieldname(account_name):
	# ERPNext fieldnames cannot contain spaces or special chars
	import re
	safe = re.sub(r'[^a-zA-Z0-9]', '_', account_name)
	# Fieldnames can't be too long, but dictionaries don't strictly care in script reports. 
	# However, frappe datatable sometimes complains if fieldnames are weird.
	return safe.lower()