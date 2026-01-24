import frappe
from frappe import _
from collections import defaultdict

RENT_STATUS_RETURNED = "Returned"
RENT_STATUS_PARTIAL_RETURNED = "Partial Returned"
RENT_STATUS_SUBMITTED = "Submitted"

def before_cancel(doc, method):
    """
    BEFORE Sales Invoice cancel (runs before validation):
    Fully unlink all references between Rent, Stock Entry, and Sales Invoice
    to avoid 'linked document' errors during cancellation.
    """
    try:
        rent_name = doc.get("rent")
        if rent_name:
            # Unlink sales_invoice and stock_entry from Rent
            frappe.db.set_value("Rent", rent_name, "sales_invoice", None)
            frappe.db.set_value("Rent", rent_name, "sales_invoice_status", None)
            frappe.db.set_value("Rent", rent_name, "stock_entry", None)
        # Find all related Stock Entries
        stock_entries = frappe.get_all(
            "Stock Entry",
            filters={"sales_invoice": doc.name, "docstatus": 1},
            pluck="name"
        )
        # Unlink rent from all Stock Entries
        for stock_entry_name in stock_entries:
            frappe.db.set_value("Stock Entry", stock_entry_name, "rent", None)
            frappe.db.set_value("Stock Entry", stock_entry_name, "sales_invoice", None)
        # Unlink rent and stock_entry from Sales Invoice
        frappe.db.set_value("Sales Invoice", doc.name, "rent", None)
        if hasattr(doc, "stock_entry"):
            frappe.db.set_value("Sales Invoice", doc.name, "stock_entry", None)
    except Exception as e:
        frappe.log_error(str(e), "Sales Invoice Before Cancel Error")

def on_submit(doc, method):
    """
    يتم استدعاؤها عند اعتماد فاتورة مبيعات.

    تقوم بالتحقق من وجود حقل Rent المخصص في الفاتورة،
    ثم تستدعي الدالة update_rent_status لتحديث حالة Rent.

    Args:
        doc (frappe.Document): فاتورة المبيعات.
        method (str): اسم الطريقة التي تم استدعاء الدالة بواسطتها.
    """
    if doc.get("rent"):
        try:
            rent_doc = frappe.get_doc("Rent", doc.rent)
            update_rent_status(rent_doc, doc)
            create_stock_entry(doc)
        except frappe.DoesNotExistError:
            frappe.msgprint(_("Rent document {} does not exist.").format(doc.rent), raise_exception=True)
    else:
        # يمكنك اختيارياً طباعة رسالة هنا إذا كان عدم وجود Rent أمرًا غير متوقع
        # frappe.msgprint(_("Rent is not linked to this Sales Invoice."))
        pass
# def on_update_after_submit(doc, method):
#     rent_doc = frappe.get_doc("Rent", doc.rent)
#     frappe.db.set_value('Rent', rent_doc.name , 'sales_invoice_status', doc.status)
def on_change(doc, method):
    if doc.get("rent"):
        frappe.db.set_value("Rent", doc.rent, "sales_invoice_status", doc.status)

def on_cancel(doc, method):
    """
    On Sales Invoice cancel (after validation):
    1. Cancel all related Stock Entries
    2. Update Rent status to 'Submitted'
    """
    try:
        rent_name = doc.get("rent")
        # Find all related Stock Entries
        stock_entries = frappe.get_all(
            "Stock Entry",
            filters={"sales_invoice": doc.name, "docstatus": 1},
            pluck="name"
        )
        # Cancel all Stock Entries
        for stock_entry_name in stock_entries:
            stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)
            stock_entry.cancel()
        # Update Rent status
        if rent_name:
            frappe.db.set_value("Rent", rent_name, "status", RENT_STATUS_SUBMITTED)
    except Exception as e:
        frappe.log_error(str(e), "Sales Invoice Cancel Error")
        frappe.msgprint(_("Error during cancellation: {0}").format(str(e)), alert=True, indicator='red')



def update_rent_status(rent_doc, sales_invoice_doc):
    """
    تقوم بالتحقق من الأصناف والكميات في فاتورة المبيعات
    ومقارنتها بالـ time_logs في الـ Rent والفواتير السابقة.
    بناءً على النتيجة، يتم تحديث حقل الـ Status إلى "Returned" أو "Partial Returned".

    Args:
        rent_doc (frappe.Document): مستند Rent.
        sales_invoice_doc (frappe.Document): فاتورة المبيعات الحالية.
    """
    from collections import defaultdict

    expected_items = defaultdict(float)  # الكميات المتوقعة من الـ Rent
    actual_items = defaultdict(float)    # الكميات الفعلية من الفواتير

    # تجميع الأصناف والكميات المتوقعة من الـ Time Logs
    for log in rent_doc.time_logs:
        expected_items[log.item_code] += log.qty

    # استرجاع الفواتير السابقة واستخراج الكميات المرتجعة منها
    previous_invoices = frappe.get_all(
        "Sales Invoice Item",
        fields=["item_code", "rent_qty"],
        filters={
            "parenttype": "Sales Invoice",
            "parent": ["in", frappe.get_all(
                "Sales Invoice",
                filters={"rent": rent_doc.name, "docstatus": 1, "name": ["!=", sales_invoice_doc.name]},
                pluck="name"
            )]
        }
    )

    # تجميع الكميات المرتجعة من الفواتير السابقة
    for item in previous_invoices:
        actual_items[item.item_code] += item.rent_qty

    # تجميع الكميات المرتجعة من الفاتورة الحالية
    for item in sales_invoice_doc.items:
        actual_items[item.item_code] += item.rent_qty

    is_returned = True
    is_partial_returned = False

    # التحقق من إرجاع جميع الأصناف بالكميات المتوقعة
    for item_code, expected_qty in expected_items.items():
        if actual_items.get(item_code, 0) < expected_qty:
            is_returned = False
            break

    # التحقق من وجود إرجاع جزئي إذا لم يكن الإرجاع كاملاً
    if not is_returned:
        for item_code, actual_qty in actual_items.items():
            if item_code in expected_items and actual_qty > 0:
                is_partial_returned = True
                break

    # تحديث حالة الـ Rent بناءً على النتائج
    if is_returned:
        frappe.db.set_value('Rent', rent_doc.name , 'status', RENT_STATUS_RETURNED)
    elif is_partial_returned:
        frappe.db.set_value('Rent', rent_doc.name , 'status', RENT_STATUS_PARTIAL_RETURNED)
    frappe.db.set_value('Rent', rent_doc.name , 'sales_invoice', sales_invoice_doc.name) 
def create_stock_entry(doc):
    """
    يتم استدعاؤها عند اعتماد المستند.
    تقوم بإنشاء Stock Entry.
    """
    # إنشاء Stock Entry
    new_doc = frappe.get_doc({
        'doctype': 'Stock Entry',
        'transaction_date': doc.posting_date,
        'stock_entry_type': 'Material Transfer',
        'customer': doc.customer,
        'rent': doc.rent,
        'from_warehouse': doc.from_warehouse,
        'to_warehouse': doc.to_warehouse,
        'sales_invoice': doc.name,
    })
    for d in doc.items:
        new = new_doc.append("items", {})
        new.item_code = d.item_code
        new.item_name = d.item_name
        new.qty = d.rent_qty
        new.s_warehouse = doc.from_warehouse  # Set source warehouse from parent
        new.t_warehouse = doc.to_warehouse    # Set target warehouse from parent
        new.customer = doc.customer
        new.cost_center = doc.cost_center
    new_doc.insert(ignore_permissions=True)
    new_doc.submit()

@frappe.whitelist()
def cancel_sales_invoice_with_unlink(sales_invoice_name, rent_name):
    """
    Unlink all references AND cancel the Sales Invoice in one operation.
    This bypasses Frappe's linked document validation.
    """
    try:
        # Step 1: Unlink from Rent
        if rent_name:
            frappe.db.set_value("Rent", rent_name, "sales_invoice", None)
            frappe.db.set_value("Rent", rent_name, "sales_invoice_status", None)
            frappe.db.set_value("Rent", rent_name, "stock_entry", None)
        
        # Step 2: Find all Stock Entries
        stock_entries = frappe.get_all(
            "Stock Entry",
            filters={"sales_invoice": sales_invoice_name, "docstatus": 1},
            pluck="name"
        )
        
        # Step 3: Unlink from Stock Entries
        for stock_entry_name in stock_entries:
            frappe.db.set_value("Stock Entry", stock_entry_name, "rent", None)
            frappe.db.set_value("Stock Entry", stock_entry_name, "sales_invoice", None)
            frappe.db.set_value("Stock Entry", stock_entry_name, "customer", None)
        
        # Step 4: Unlink from Sales Invoice
        frappe.db.set_value("Sales Invoice", sales_invoice_name, "rent", None)
        
        # Step 5: Cancel all Stock Entries
        for stock_entry_name in stock_entries:
            try:
                stock_entry_doc = frappe.get_doc("Stock Entry", stock_entry_name)
                stock_entry_doc.cancel()
            except Exception as e:
                frappe.log_error(f"Failed to cancel Stock Entry {stock_entry_name}: {str(e)}", "Cancel Stock Entry Error")
        
        # Step 6: Cancel the Sales Invoice itself
        sales_invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice_name)
        sales_invoice_doc.cancel()
        
        # Step 7: Update Rent status
        if rent_name:
            frappe.db.set_value("Rent", rent_name, "status", RENT_STATUS_SUBMITTED)
        
        frappe.db.commit()
        return f"Successfully cancelled Sales Invoice {sales_invoice_name} and all related Stock Entries."
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(str(e), "Cancel Sales Invoice With Unlink Error")
        raise frappe.ValidationError(f"Error during cancellation: {str(e)}")

@frappe.whitelist()
def unlink_all_before_cancel(sales_invoice_name, rent_name):
    """
    Unlink all references before cancellation.
    This must be called BEFORE attempting to cancel the Sales Invoice.
    """
    try:
        # Unlink from Rent
        if rent_name:
            frappe.db.set_value("Rent", rent_name, "sales_invoice", None)
            frappe.db.set_value("Rent", rent_name, "sales_invoice_status", None)
            frappe.db.set_value("Rent", rent_name, "stock_entry", None)
        
        # Find all Stock Entries
        stock_entries = frappe.get_all(
            "Stock Entry",
            filters={"sales_invoice": sales_invoice_name, "docstatus": 1},
            pluck="name"
        )
        
        # Unlink from Stock Entries
        for stock_entry_name in stock_entries:
            frappe.db.set_value("Stock Entry", stock_entry_name, "rent", None)
            frappe.db.set_value("Stock Entry", stock_entry_name, "sales_invoice", None)
            frappe.db.set_value("Stock Entry", stock_entry_name, "customer", None)
        
        # Unlink from Sales Invoice
        frappe.db.set_value("Sales Invoice", sales_invoice_name, "rent", None)
        
        return f"Successfully unlinked all references. You can now cancel the Sales Invoice."
    except Exception as e:
        frappe.log_error(str(e), "Unlink Before Cancel Error")
        return f"Error: {str(e)}"

@frappe.whitelist()
def unlink_stock_entries_from_rent(sales_invoice_name):
    """
    Unlink all Stock Entries from Rent for a given Sales Invoice.
    Call this before cancelling the Sales Invoice to avoid linked document errors.
    """
    stock_entries = frappe.get_all(
        "Stock Entry",
        filters={"sales_invoice": sales_invoice_name, "docstatus": 1},
        pluck="name"
    )
    for stock_entry_name in stock_entries:
        frappe.db.set_value("Stock Entry", stock_entry_name, "rent", None)
        frappe.db.set_value("Stock Entry", stock_entry_name, "customer", None)
    return f"Unlinked {len(stock_entries)} Stock Entries from Rent for Sales Invoice {sales_invoice_name}."
