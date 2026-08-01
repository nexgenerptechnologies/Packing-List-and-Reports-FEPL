import frappe
from frappe import _
from frappe.utils import flt
import re

def execute(filters=None):
	if not filters:
		filters = {}

	if not filters.get("company"):
		filters["company"] = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value('Global Defaults', 'default_company')

	# Ensure defensive default dates
	filters.setdefault("from_date", "1900-01-01")
	filters.setdefault("to_date", "2100-12-31")

	data = get_data(filters)
	columns = get_columns(filters, data)

	return columns, data

def get_columns(filters, data):
	columns = [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 130},
		{"label": _("Vch No."), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 150},
		{"label": _("Particulars"), "fieldname": "party_name", "fieldtype": "Data", "width": 220},
		{"label": _("Bill No / Ref"), "fieldname": "bill_no", "fieldtype": "Data", "width": 150},
		{"label": _("Total Gross Value"), "fieldname": "total_gross_value", "fieldtype": "Currency", "width": 140}
	]
	
	# Dynamically add account columns found in the data
	dynamic_columns = build_account_columns(data)
	columns.extend(dynamic_columns)
	
	return columns

def get_data(filters):
	conditions = get_conditions(filters)
	
	# 1. Fetch only vouchers that have at least one debit to an Expense, Tax, or Asset account (e.g. Customs, Freight)
	# This strictly eliminates Customer Payment Entries and pure transfers!
	vouchers_with_expenses = frappe.db.sql("""
		SELECT DISTINCT gle.voucher_no
		FROM `tabGL Entry` gle
		JOIN `tabAccount` acc ON gle.account = acc.name
		WHERE gle.is_cancelled = 0
		AND (acc.root_type = 'Expense' OR acc.account_type IN ('Tax', 'Chargeable', 'Expense Account', 'Expenses Included In Valuation'))
		AND gle.debit > 0
		{conditions}
	""".format(conditions=conditions), filters, as_dict=1)

	if not vouchers_with_expenses:
		return []

	voucher_list = [v.voucher_no for v in vouchers_with_expenses]

	# 2. Fetch all GL entries for these specific expense vouchers
	gl_entries = frappe.db.sql("""
		SELECT 
			posting_date, voucher_type, voucher_no, account, party_type, party, 
			debit, credit, against_voucher, remarks, bill_no
		FROM `tabGL Entry`
		WHERE is_cancelled = 0 
		AND voucher_no IN %s
		ORDER BY posting_date ASC, voucher_no ASC
	""", (tuple(voucher_list),), as_dict=1)

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
		posting_date = entries[0].posting_date
		
		# Find the Supplier / Main Source of Credit
		party_name = ""
		bill_no = ""
		
		# Look for actual party
		for gle in entries:
			if gle.party:
				party_name = gle.party
			if gle.bill_no or gle.against_voucher:
				bill_no = gle.bill_no or gle.against_voucher

		# If no party, find the main credited account (e.g. Bank or Cash)
		if not party_name:
			credits = [e for e in entries if e.credit > 0]
			if credits:
				credits.sort(key=lambda x: x.credit, reverse=True)
				party_name = credits[0].account

		if not bill_no:
			bill_no = v_no

		# Calculate total gross value (Total Credit to the party/source)
		total_gross_value = sum(e.credit for e in entries)

		account_amounts = {}
		for gle in entries:
			# Skip the source party account from the dynamic columns
			if gle.party and gle.party == party_name:
				continue
			if not gle.party and gle.account == party_name:
				continue
				
			net_amount = flt(gle.debit) - flt(gle.credit)
			if net_amount != 0:
				account_amounts[gle.account] = account_amounts.get(gle.account, 0.0) + net_amount

		row = {
			"posting_date": posting_date,
			"voucher_type": v_type,
			"voucher_no": v_no,
			"party_name": party_name,
			"bill_no": bill_no,
			"total_gross_value": total_gross_value,
		}
		
		# Merge the dynamic account amounts into the row dictionary
		for acc, amt in account_amounts.items():
			safe_acc = get_safe_fieldname(acc)
			row[safe_acc] = amt
			# Store the original readable account name in the row metadata so columns use the exact Chart of Accounts name!
			row["_acc_name_" + safe_acc] = acc
			
		data.append(row)

	return data

def get_conditions(filters):
	conditions = ""
	if filters.get("company"):
		conditions += " AND gle.company = %(company)s"
	if filters.get("from_date"):
		conditions += " AND gle.posting_date >= %(from_date)s"
	if filters.get("to_date"):
		conditions += " AND gle.posting_date <= %(to_date)s"
	if filters.get("voucher_type"):
		conditions += " AND gle.voucher_type = %(voucher_type)s"
	if filters.get("party"):
		conditions += " AND gle.party = %(party)s"
	return conditions

def build_account_columns(data):
	# Scan all data rows to find dynamic account columns and their exact real names
	dynamic_fields = {}
	for row in data:
		for key, val in row.items():
			if key.startswith("_acc_name_"):
				safe_key = key.replace("_acc_name_", "")
				dynamic_fields[safe_key] = val
				
	columns = []
	for safe_key in sorted(dynamic_fields.keys()):
		real_name = dynamic_fields[safe_key]
		# Shorten the label by removing company abbreviation if present (e.g. ' - FEPL')
		clean_label = re.sub(r' - [A-Za-z0-9]+$', '', real_name).upper()
		columns.append({
			"label": clean_label,
			"fieldname": safe_key,
			"fieldtype": "Currency",
			"width": 150
		})
		
	return columns

def get_safe_fieldname(account_name):
	# ERPNext fieldnames cannot contain spaces or special chars
	safe = re.sub(r'[^a-zA-Z0-9]', '_', account_name)
	return safe.lower()