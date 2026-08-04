import frappe
from frappe import _
from frappe.utils import flt
import re
import json

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
	account_list = get_accounts_filter(filters)
	party_list = get_parties_filter(filters)
	
	# If accounts are filtered:
	if account_list:
		account_condition = " AND gle.account IN %(selected_accounts)s"
		filters["selected_accounts"] = tuple(account_list)
	else:
		account_condition = " AND (acc.root_type = 'Expense' OR acc.account_type IN ('Tax', 'Chargeable', 'Expense Account', 'Expenses Included In Valuation'))"

	# If parties are filtered:
	if party_list:
		party_condition = """
			AND gle.voucher_no IN (
				SELECT DISTINCT voucher_no 
				FROM `tabGL Entry` 
				WHERE party IN %(selected_parties)s AND is_cancelled = 0
			)
		"""
		filters["selected_parties"] = tuple(party_list)
	else:
		party_condition = ""

	# 1. Fetch vouchers that match the selected expense accounts or all general expenses, and party condition
	vouchers_with_expenses = frappe.db.sql("""
		SELECT DISTINCT gle.voucher_no
		FROM `tabGL Entry` gle
		JOIN `tabAccount` acc ON gle.account = acc.name
		WHERE gle.is_cancelled = 0
		AND gle.debit > 0
		{account_condition}
		{party_condition}
		{conditions}
	""".format(account_condition=account_condition, party_condition=party_condition, conditions=conditions), filters, as_dict=1)

	if not vouchers_with_expenses:
		return []

	voucher_list = [v.voucher_no for v in vouchers_with_expenses]

	# Fetch supplier invoice number (bill_no) from Purchase Invoices
	pi_bill_map = {}
	try:
		pi_data = frappe.db.sql("""
			SELECT name, bill_no FROM `tabPurchase Invoice` WHERE name IN %s
		""", (tuple(voucher_list),), as_dict=1)
		for pi in pi_data:
			if pi.bill_no:
				pi_bill_map[pi.name] = pi.bill_no
	except Exception:
		pass

	# 2. Fetch all GL entries for these specific expense vouchers
	gl_entries = frappe.db.sql("""
		SELECT 
			posting_date, voucher_type, voucher_no, account, party_type, party, 
			debit, credit, against_voucher, remarks
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
			if gle.against_voucher:
				bill_no = gle.against_voucher

		if not bill_no and v_no in pi_bill_map:
			bill_no = pi_bill_map[v_no]

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
	return conditions

def get_parties_filter(filters):
	raw_party = filters.get("party")
	if not raw_party:
		return []
	
	if isinstance(raw_party, str):
		try:
			parsed = json.loads(raw_party)
			if isinstance(parsed, list):
				raw_party = parsed
			else:
				raw_party = [raw_party]
		except Exception:
			raw_party = [raw_party]
	elif not isinstance(raw_party, list):
		raw_party = [raw_party]

	return [p.strip() for p in raw_party if p and p.strip()]

def get_accounts_filter(filters):
	raw_account = filters.get("account")
	if not raw_account:
		return []
	
	if isinstance(raw_account, str):
		try:
			parsed = json.loads(raw_account)
			if isinstance(parsed, list):
				raw_account = parsed
			else:
				raw_account = [raw_account]
		except Exception:
			raw_account = [raw_account]
	elif not isinstance(raw_account, list):
		raw_account = [raw_account]

	# Expand group accounts to include all child accounts (just like standard General Ledger)
	expanded_accounts = set()
	for acc in raw_account:
		if not acc:
			continue
		acc_info = frappe.db.get_value("Account", acc, ["is_group", "lft", "rgt"], as_dict=1)
		if acc_info and acc_info.is_group:
			children = frappe.db.sql_list("""
				SELECT name FROM `tabAccount` WHERE lft >= %s AND rgt <= %s
			""", (acc_info.lft, acc_info.rgt))
			expanded_accounts.update(children)
		else:
			expanded_accounts.add(acc)
			
	return list(expanded_accounts)

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