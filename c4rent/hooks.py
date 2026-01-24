app_name = "c4rent"
app_title = "C4Rent"
app_publisher = "Connect 4 Systems"
app_description = "Daily Rent Operation"
app_email = "t.algazzar@gmail.com"
app_license = "mit"
# required_apps = []

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/c4rent/css/swiper/swiper-bundle.min.css"
app_include_js = "/assets/c4rent/js/swiper/swiper-bundle.min.js"

# include js, css files in header of web template
# web_include_css = "/assets/c4rent/css/c4rent.css"
# web_include_js = "/assets/c4rent/js/c4rent.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "c4rent/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Sales Invoice" : "public/js/sales_invoice.js"
    }
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "c4rent/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#	"methods": "c4rent.utils.jinja_methods",
#	"filters": "c4rent.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "c4rent.install.before_install"
# after_install = "c4rent.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "c4rent.uninstall.before_uninstall"
# after_uninstall = "c4rent.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "c4rent.utils.before_app_install"
# after_app_install = "c4rent.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "c4rent.utils.before_app_uninstall"
# after_app_uninstall = "c4rent.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "c4rent.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"Sales Invoice": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Sales Invoice": {
        "before_cancel": "c4rent.c4rent.doc_events.sales_invoice.before_cancel",
        "on_submit": "c4rent.c4rent.doc_events.sales_invoice.on_submit",
        "on_change": "c4rent.c4rent.doc_events.sales_invoice.on_change",
        "on_cancel": "c4rent.c4rent.doc_events.sales_invoice.on_cancel"
    },
    "Payment Entry": {
        "on_submit": "c4rent.c4rent.doc_events.payment_entry.on_submit"
    },
    "Stock Entry": {
        "before_insert": "c4rent.c4rent.doc_events.stock_entry.before_insert",
        "before_save": "c4rent.c4rent.doc_events.stock_entry.before_save"
    }
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
#	"all": [
#		"c4rent.tasks.all"
#	],
#	"daily": [
#		"c4rent.tasks.daily"
#	],
#	"hourly": [
#		"c4rent.tasks.hourly"
#	],
#	"weekly": [
#		"c4rent.tasks.weekly"
#	],
#	"monthly": [
#		"c4rent.tasks.monthly"
#	],
# }

# Testing
# -------

# before_tests = "c4rent.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#	"frappe.desk.doctype.event.event.get_events": "c4rent.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#	"Task": "c4rent.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["c4rent.utils.before_request"]
# after_request = ["c4rent.utils.after_request"]

# Job Events
# ----------
# before_job = ["c4rent.utils.before_job"]
# after_job = ["c4rent.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
#	{
#		"doctype": "{doctype_1}",
#		"filter_by": "{filter_by}",
#		"redact_fields": ["{field_1}", "{field_2}"],
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_2}",
#		"filter_by": "{filter_by}",
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_3}",
#		"strict": False,
#	},
#	{
#		"doctype": "{doctype_4}"
#	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#	"c4rent.auth.validate"
# ]
fixtures = [
    {
        "doctype": "Client Script",
        "filters": [
            ["name", "in", ["Rent"]]
        ]
    },
]