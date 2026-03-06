# Copyright (c) 2023, Connect 4 Systems and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


def get_allowed_pos_profiles(user):
    """Return enabled POS Profiles explicitly assigned to a user."""
    assigned_profiles = frappe.get_all(
        "POS Profile User",
        filters={"user": user, "parenttype": "POS Profile"},
        pluck="parent",
    )

    if not assigned_profiles:
        return []

    return frappe.get_all(
        "POS Profile",
        filters={"name": ["in", assigned_profiles], "disabled": 0},
        order_by="name asc",
        pluck="name",
    )


@frappe.whitelist()
def get_user_pos_profiles(user=None):
    """Expose allowed POS Profiles for the current user to client scripts."""
    user = user or frappe.session.user
    profiles = get_allowed_pos_profiles(user)
    return {
        "profiles": profiles,
        "default_profile": profiles[0] if len(profiles) == 1 else None,
    }


def get_pos_profile_item_groups(pos_profile):
    """Return distinct item groups from POS Profile item group child table."""
    item_groups = []
    if not pos_profile:
        return item_groups

    for row in pos_profile.get("item_groups") or []:
        item_group = row.get("item_group")
        if item_group and item_group not in item_groups:
            item_groups.append(item_group)

    return item_groups

class Rent(Document):

    def _get_pos_profile_doc(self):
        if not self.pos_profile:
            return None
        return frappe.get_cached_doc("POS Profile", self.pos_profile)

    def get_price_list_for_rent_type(self):
        pos_profile = self._get_pos_profile_doc()
        if not pos_profile:
            return None

        if self.rent_type == "Monthly":
            return pos_profile.custom_monthly_price_list

        return pos_profile.selling_price_list

    @staticmethod
    def get_pos_profile_print_heading(pos_profile):
        return getattr(pos_profile, "print_heading", None) or getattr(pos_profile, "select_print_heading", None)

    def apply_pos_profile_defaults(self):
        """Fill Rent defaults from selected POS Profile if values are missing."""
        pos_profile = self._get_pos_profile_doc()
        if not pos_profile:
            return

        if not self.source_warehouse and pos_profile.warehouse:
            self.source_warehouse = pos_profile.warehouse

        if not self.target_warehouse and pos_profile.custom_default_target_warehouse:
            self.target_warehouse = pos_profile.custom_default_target_warehouse

        pos_profile_item_groups = get_pos_profile_item_groups(pos_profile)
        if not self.item_group and pos_profile_item_groups:
            self.item_group = pos_profile_item_groups[0]

    def validate_pos_profile_access(self):
        if not self.pos_profile:
            frappe.throw(_("POS Profile is required for Rent."))

        allowed_profiles = get_allowed_pos_profiles(frappe.session.user)

        if not allowed_profiles:
            frappe.throw(
                _("No POS Profile is assigned to user {0}.").format(frappe.bold(frappe.session.user))
            )

        if self.pos_profile not in allowed_profiles:
            frappe.throw(
                _("You are not allowed to use POS Profile {0}.").format(frappe.bold(self.pos_profile))
            )

    def validate_pos_profile_configuration(self):
        pos_profile = self._get_pos_profile_doc()
        if not pos_profile:
            return

        if not pos_profile.custom_default_target_warehouse:
            frappe.throw(
                _("Default Target Warehouse is required in POS Profile {0}.").format(
                    frappe.bold(self.pos_profile)
                )
            )

        if not self.source_warehouse:
            frappe.throw(
                _("Source Warehouse is required. Set Warehouse in POS Profile {0} or on Rent.").format(
                    frappe.bold(self.pos_profile)
                )
            )

        if not self.target_warehouse:
            frappe.throw(
                _("Target Warehouse is required. Set Default Target Warehouse in POS Profile {0} or on Rent.").format(
                    frappe.bold(self.pos_profile)
                )
            )

        if self.rent_type == "Daily" and not pos_profile.selling_price_list:
            frappe.throw(
                _("Price List is required in POS Profile {0} for Daily rent.").format(
                    frappe.bold(self.pos_profile)
                )
            )

        if self.rent_type == "Monthly" and not pos_profile.custom_monthly_price_list:
            frappe.throw(
                _("Monthly Price List is required in POS Profile {0} for Monthly rent.").format(
                    frappe.bold(self.pos_profile)
                )
            )

    def before_validate(self):
        """
        Calculate total quantity and amount from time logs.
        Convert None rates to 0 to prevent calculation errors.
        """
        self.apply_pos_profile_defaults()

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
        self.validate_pos_profile_access()
        self.validate_pos_profile_configuration()
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
        frappe.db.set_value("Rent", self.name, "stock_entry", new_doc.name)

        # تحديث حالة Rent إلى "Submitted"
        self.db_set('status', 'Submitted')

        # إنشاء Sales Invoice إذا كان نوع الإيجار شهريًا
        if self.rent_type == "Monthly":
            pos_profile = self._get_pos_profile_doc()
            monthly_price_list = self.get_price_list_for_rent_type() or "Monthly"
            new_invoice = frappe.get_doc({
                'doctype': 'Sales Invoice',
                'transaction_date': self.date,
                'customer': self.customer,
                'rent': self.name,
                'pos_profile': self.pos_profile,
                "reference_name": self.name,
                "reference_doctype": "Rent",
                "selling_price_list": monthly_price_list,
                "letter_head": pos_profile.letter_head if pos_profile else None,
                "select_print_heading": self.get_pos_profile_print_heading(pos_profile) if pos_profile else None,
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
            frappe.db.set_value("Rent", self.name, "sales_invoice", new_invoice.name)

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
        filters = {"in_slider": 1}
        pos_profile = self._get_pos_profile_doc()
        pos_profile_item_groups = get_pos_profile_item_groups(pos_profile)

        if pos_profile_item_groups:
            filters = {"name": ["in", pos_profile_item_groups]}

        item_group = frappe.get_list("Item Group",
            fields=["name", "image"],
            filters=filters,
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