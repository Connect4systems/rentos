# Copyright (c) 2023, Connect 4 Systems and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import datetime
import json
from frappe import _

class Rent(Document):

    def before_validate(self):
        """
        Calculate total quantity and amount from time logs.
        Convert None rates to 0 to prevent calculation errors.
        """
        tot_qty = 0
        tot_amt = 0
        for d in self.time_logs:
            # Ensure rate is not None; default to 0
            if d.rate is None:
                d.rate = 0
            d.amount = d.qty * d.rate
            tot_qty += d.qty
            tot_amt += d.amount
        self.total_qty = tot_qty
        self.price_per_day_or_month = tot_amt

    def validate(self):
        """
        يتم استدعاؤها للتحقق من صحة المستند.
        يمكنك إضافة قواعد التحقق هنا.
        """
        pass
    	# if doc.rent_type == "Daily" and doc.is_new():
		# 	for x in doc.time_logs:
		# 		x.rate = frappe.db.get_value('Item Price', {"item_code": x.item_code, "selling" : 1,"price_list": "Daily"}, 'price_list_rate') or 0
		# 		x.income_account = frappe.db.get_single_value('Company', 'default_income_account')
		# elif doc.rent_type == "Monthly" and doc.is_new():
		# 	for x in doc.time_logs:
		# 		x.rate = frappe.db.get_value('Item Price', {"item_code": x.item_code, "selling" : 1,"price_list": "Monthly"}, 'price_list_rate') or 0
		# 		x.income_account = frappe.db.get_single_value('Company', 'default_income_account')

    def on_submit(self):
        """
        يتم استدعاؤها عند اعتماد المستند.
        تقوم بإنشاء Stock Entry و Sales Invoice (إذا كان نوع الإيجار شهريًا).
        """
        # إنشاء Stock Entry
        new_doc = frappe.get_doc({
            'doctype': 'Stock Entry',
            'transaction_date': self.date,
            'stock_entry_type': 'Material Transfer',
            'customer': self.customer,
            'rent': self.name,
            'from_warehouse': self.source_warehouse,
            'to_warehouse': self.target_warehouse,
        })
        for d in self.time_logs:
            new = new_doc.append("items", {})
            new.item_code = d.item_code
            new.item_name = d.item_name
            new.qty = d.qty
            new.s_warehouse = self.source_warehouse  # Set source warehouse from parent
            new.t_warehouse = self.target_warehouse  # Set target warehouse from parent
            new.cost_center = self.cost_center
            new.customer = self.customer
        new_doc.insert(ignore_permissions=True)
        new_doc.submit()
        frappe.db.sql(f"""
            UPDATE tabRent SET stock_entry = '{new_doc.name}' WHERE name = '{self.name}'
        """)

        # تحديث حالة Rent إلى "Submitted"
        self.db_set('status', 'Submitted')

        # إنشاء Sales Invoice إذا كان نوع الإيجار شهريًا
        if self.rent_type == "Monthly":
            new_invoice = frappe.get_doc({
                'doctype': 'Sales Invoice',
                'transaction_date': self.date,
                'customer': self.customer,
                'rent': self.name,
                "reference_name": self.name,
                "reference_doctype": "Rent",
                "selling_price_list": "Monthly",
                'from_warehouse': self.source_warehouse,
                'to_warehouse': self.target_warehouse,
            })
            for d in self.time_logs:
                new = new_invoice.append("items", {})
                new.item_code = d.item_code
                new.item_name = d.item_name
                new.qty = d.qty
                new.rate = d.rate
            new_invoice.insert(ignore_permissions=True)
            new_invoice.submit()
            frappe.db.sql(f"""
            UPDATE tabRent JOIN tabSales Invoice 
            ON tabRent.name = tabSales Invoice.rent 
            SET tabRent.sales_invoice = '{new_invoice.name}' 
            WHERE tabSales Invoice.rent = '{self.name}' AND selling_price_list='Monthly'
            """)

    @frappe.whitelist()
    def stop_auto_repeat(self):
        """
        يتم استدعاؤها لإيقاف التكرار التلقائي للفواتير.
        """
        auto_repeat_list = frappe.get_list(
            "Auto Repeat",
            filters={"reference_document": self.sales_invoice}
        )
        for auto_repeat in auto_repeat_list:
            auto_repeat_doc = frappe.get_doc("Auto Repeat", auto_repeat.name)
            auto_repeat_doc.disabled = 1
            auto_repeat_doc.save()
        #frappe.db.sql(f"""UPDATE tabRent SET status = "Returned" WHERE name = '{self.name}'""")
        new_doc = frappe.get_doc({
            'doctype': 'Stock Entry',
            'transaction_date': self.date,
            'stock_entry_type': 'Material Transfer',
            'customer': self.customer,
            'rent': self.name,
            'from_warehouse': self.target_warehouse,
            'to_warehouse': self.source_warehouse,
        })
        for d in self.time_logs:
            new = new_doc.append("items", {})
            new.item_code = d.item_code
            new.item_name = d.item_name
            new.qty = d.qty
            new.s_warehouse = self.target_warehouse  # Set source warehouse from parent (reversed)
            new.t_warehouse = self.source_warehouse  # Set target warehouse from parent (reversed)
            new.customer = self.customer
        new_doc.insert(ignore_permissions=True)
        new_doc.submit()
        self.reload()

    def on_cancel(self):
        """
        يتم استدعاؤها عند إلغاء المستند.
        """
        self.ignore_linked_doctypes = ["Stock Entry"]
    @frappe.whitelist()
    def get_item_group(self):
        """
        يتم استدعاؤها للحصول على مجموعات الأصناف.
        """
        item_group = frappe.get_list("Item Group",
            fields=["name", "image"],
            filters={
                'in_slider': 1
            },
        )
        for ig in item_group:
            if ig.image:
                ig.image = f"{frappe.utils.get_url()}/{ig.image}"
        return item_group

    @frappe.whitelist()
    def get_item_group_details(self, item_group):
        """
        يتم استدعاؤها للحصول على تفاصيل مجموعة الأصناف.
        """
        if not item_group:
            return {}

        try:
            item_group_doc = frappe.get_doc("Item Group", item_group)
            return {
                "name": item_group_doc.name,
                "file_image": frappe.utils.get_file_link(item_group_doc.image),
            }
        except Exception as e:
            frappe.log_error(_("Item Group '{0}' not found. Error: {1}").format(item_group, str(e)), "get_package_details")
            return {}

    @frappe.whitelist()
    def get_items(self, item_group):
        """
        يتم استدعاؤها للحصول على الأصناف المرتبطة بمجموعة الأصناف.
        """
        if not item_group:
            return []

        try:
            items = frappe.get_all('Item', fields=['name', 'item_name','image'], filters={'item_group': item_group})
            for i in items:
                if i.image:
                    i.image = f"{frappe.utils.get_url()}/{i.image}"
                return items
        except Exception as e:
            frappe.log_error(_("Error fetching items for Item Group '{0}'. Error: {1}").format(item_group, str(e)), "get_items")
            return []

@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
    doc = frappe.get_doc("Rent", source_name)
    payment_entry = frappe.new_doc("Payment Entry")
    payment_entry.payment_type = "Receive"
    payment_entry.party_type = "Customer"
    payment_entry.party = doc.customer
    payment_entry.party_name = doc.customer
    payment_entry.rent = doc.name
    return payment_entry

@frappe.whitelist()
def full_unlink_rent(rent_name):
    """
    Unlink all references between Rent, Stock Entry, and Sales Invoice for a given Rent document.
    This is useful to run before cancelling any document to avoid linked document errors.
    """
    rent_doc = frappe.get_doc("Rent", rent_name)
    # Unlink sales_invoice and stock_entry from Rent
    frappe.db.set_value("Rent", rent_name, "sales_invoice", None)
    frappe.db.set_value("Rent", rent_name, "sales_invoice_status", None)
    frappe.db.set_value("Rent", rent_name, "stock_entry", None)
    # Unlink rent from all Stock Entries
    stock_entries = frappe.get_all(
        "Stock Entry",
        filters={"rent": rent_name, "docstatus": 1},
        pluck="name"
    )
    for stock_entry_name in stock_entries:
        frappe.db.set_value("Stock Entry", stock_entry_name, "rent", None)
        frappe.db.set_value("Stock Entry", stock_entry_name, "sales_invoice", None)
    # Unlink rent from all Sales Invoices
    sales_invoices = frappe.get_all(
        "Sales Invoice",
        filters={"rent": rent_name, "docstatus": 1},
        pluck="name"
    )
    for sinv_name in sales_invoices:
        frappe.db.set_value("Sales Invoice", sinv_name, "rent", None)
        frappe.db.set_value("Sales Invoice", sinv_name, "stock_entry", None)
    # Update Rent status
    frappe.db.set_value("Rent", rent_name, "status", "Submitted")
    return f"Unlinked Rent {rent_name} from all related documents and reset status."