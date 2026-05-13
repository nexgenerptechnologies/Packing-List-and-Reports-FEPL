app_name = "packing_list_reports_fepl"
app_title = "Packing List Reports FEPL"
app_publisher = "NexGen ERP Technologies"
app_description = "Packing List and Reports for FEPL"
app_email = "admin@example.com"
app_license = "mit"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/packing_list_reports_fepl/css/packing_list_reports_fepl.css"
# app_include_js = "/assets/packing_list_reports_fepl/js/packing_list_reports_fepl.js"

# include js, css files in header of web template
# web_include_css = "/assets/packing_list_reports_fepl/css/packing_list_reports_fepl.css"
# web_include_js = "/assets/packing_list_reports_fepl/js/packing_list_reports_fepl.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "packing_list_reports_fepl/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "packing_list_reports_fepl/public/images/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "packing_list_reports_fepl.utils.jinja_methods",
# 	"filters": "packing_list_reports_fepl.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "packing_list_reports_fepl.install.before_install"
# after_install = "packing_list_reports_fepl.install.after_install"

# Uninstallation
# --------------

# before_uninstall = "packing_list_reports_fepl.uninstall.before_uninstall"
# after_uninstall = "packing_list_reports_fepl.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "packing_list_reports_fepl.utils.before_app_install"
# after_app_install = "packing_list_reports_fepl.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "packing_list_reports_fepl.utils.before_app_uninstall"
# after_app_uninstall = "packing_list_reports_fepl.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "packing_list_reports_fepl.notifications.get_notification_config"

# Permissions
# -----------
# Permissions & roles will be synced for advertised doctypes from this config

# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"packing_list_reports_fepl.tasks.all"
# 	],
# 	"daily": [
# 		"packing_list_reports_fepl.tasks.daily"
# 	],
# 	"hourly": [
# 		"packing_list_reports_fepl.tasks.hourly"
# 	],
# 	"weekly": [
# 		"packing_list_reports_fepl.tasks.weekly"
# 	],
# 	"monthly": [
# 		"packing_list_reports_fepl.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "packing_list_reports_fepl.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "packing_list_reports_fepl.event.get_events"
# }
#
# each method should be in the format 'orig_method_path': 'new_method_path'
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "packing_list_reports_fepl.event.get_events"
# }

# Ad Tags for Website
# ------------------

# jinja = {
# 	"methods": "packing_list_reports_fepl.utils.jinja_methods",
# 	"filters": "packing_list_reports_fepl.utils.jinja_filters"
# }
