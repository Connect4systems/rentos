import frappe
from frappe import _

def update_rent_field(doc, method):
    """
    تُستدعى عند تقديم Payment Entry.
    تُنسخ قيمة 'rent' من الفاتورة المرتبطة إلى حقل 'rent' في Payment Entry.
    """
    if doc.references:
        for reference in doc.references:
            if reference.reference_doctype == "Sales Invoice":
                # استرجاع فاتورة المبيعات المرتبطة
                sales_invoice = frappe.get_doc("Sales Invoice", reference.reference_name)
                if sales_invoice.rent:
                    # تحديث حقل 'rent' في Payment Entry
                    frappe.db.set_value("Payment Entry", doc.name, "rent", sales_invoice.rent)
                    break  # توقف إذا وجدت فاتورة مرتبطة

def on_submit(doc, method):
    update_rent_field(doc, method)