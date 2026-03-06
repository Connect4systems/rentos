from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

RENT_STATUS_RETURNED = "Returned"
RENT_STATUS_PARTIAL_RETURNED = "Partial Returned"
RENT_STATUS_SUBMITTED = "Submitted"


def _get_related_submitted_stock_entries(sales_invoice_name):
    if not sales_invoice_name:
        return []

    return frappe.get_all(
        "Stock Entry",
        filters={"sales_invoice": sales_invoice_name, "docstatus": 1},
        order_by="creation asc",
        pluck="name",
    )


def _cancel_related_stock_entries(stock_entry_names):
    for stock_entry_name in stock_entry_names:
        stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)
        if stock_entry.docstatus == 1:
            stock_entry.cancel()


def _wipe_links_on_stock_entries(stock_entry_names):
    for stock_entry_name in stock_entry_names:
        frappe.db.set_value(
            "Stock Entry",
            stock_entry_name,
            {"rent": None, "sales_invoice": None, "customer": None},
            update_modified=False,
        )


def _unlink_rent_references_for_cancelled_invoice(rent_name, sales_invoice_name, related_stock_entries=None):
    if not rent_name or not frappe.db.exists("Rent", rent_name):
        return

    related_stock_entries = set(related_stock_entries or [])
    rent_state = frappe.db.get_value(
        "Rent", rent_name, ["sales_invoice", "stock_entry"], as_dict=True
    ) or {}

    updates = {}
    if rent_state.get("sales_invoice") == sales_invoice_name:
        updates["sales_invoice"] = None
        updates["sales_invoice_status"] = None

    if rent_state.get("stock_entry") in related_stock_entries:
        updates["stock_entry"] = None

    if updates:
        frappe.db.set_value("Rent", rent_name, updates, update_modified=False)


def _sync_rent_status(rent_name, preferred_sales_invoice=None):
    if not rent_name or not frappe.db.exists("Rent", rent_name):
        return

    rent_doc = frappe.get_doc("Rent", rent_name)

    expected_items = defaultdict(float)
    for log in rent_doc.time_logs or []:
        expected_items[log.item_code] += flt(log.qty)

    submitted_invoices = frappe.get_all(
        "Sales Invoice",
        fields=["name", "status"],
        filters={"rent": rent_name, "docstatus": 1},
        order_by="posting_date desc, creation desc",
    )
    submitted_invoice_names = [invoice.name for invoice in submitted_invoices]

    actual_items = defaultdict(float)
    if submitted_invoice_names:
        invoice_items = frappe.get_all(
            "Sales Invoice Item",
            fields=["item_code", "rent_qty"],
            filters={
                "parenttype": "Sales Invoice",
                "parent": ["in", submitted_invoice_names],
            },
        )
        for item in invoice_items:
            actual_items[item.item_code] += flt(item.rent_qty)

    is_returned = bool(expected_items) and all(
        actual_items.get(item_code, 0) >= expected_qty
        for item_code, expected_qty in expected_items.items()
    )
    is_partial_returned = (
        not is_returned
        and any(actual_items.get(item_code, 0) > 0 for item_code in expected_items)
    )

    rent_status = RENT_STATUS_SUBMITTED
    if is_returned:
        rent_status = RENT_STATUS_RETURNED
    elif is_partial_returned:
        rent_status = RENT_STATUS_PARTIAL_RETURNED

    selected_invoice_name = None
    selected_invoice_status = None
    if submitted_invoices:
        if preferred_sales_invoice and preferred_sales_invoice in submitted_invoice_names:
            selected_invoice_name = preferred_sales_invoice
            selected_invoice_status = next(
                (invoice.status for invoice in submitted_invoices if invoice.name == preferred_sales_invoice),
                None,
            )
        else:
            selected_invoice_name = submitted_invoices[0].name
            selected_invoice_status = submitted_invoices[0].status

    frappe.db.set_value(
        "Rent",
        rent_name,
        {
            "status": rent_status,
            "sales_invoice": selected_invoice_name,
            "sales_invoice_status": selected_invoice_status,
        },
        update_modified=False,
    )


def before_cancel(doc, method):
    """Cancel and unlink Stock Entries before Sales Invoice link validation runs."""
    try:
        related_stock_entries = _get_related_submitted_stock_entries(doc.name)
        rent_name = doc.get("rent")

        doc.flags.c4rent_rent_name = rent_name
        doc.flags.c4rent_related_stock_entries = related_stock_entries

        _cancel_related_stock_entries(related_stock_entries)
        _wipe_links_on_stock_entries(related_stock_entries)
        _unlink_rent_references_for_cancelled_invoice(
            rent_name=rent_name,
            sales_invoice_name=doc.name,
            related_stock_entries=related_stock_entries,
        )

        if doc.meta.has_field("stock_entry"):
            doc.stock_entry = None
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Sales Invoice Before Cancel Error")
        raise


def on_submit(doc, method):
    if not doc.get("rent"):
        return

    try:
        rent_doc = frappe.get_doc("Rent", doc.rent)
        update_rent_status(rent_doc, doc)
        create_stock_entry(doc)
    except frappe.DoesNotExistError:
        frappe.throw(_("Rent document {0} does not exist.").format(doc.rent))


def on_change(doc, method):
    if not doc.get("rent"):
        return

    linked_invoice = frappe.db.get_value("Rent", doc.rent, "sales_invoice")
    if linked_invoice == doc.name:
        frappe.db.set_value(
            "Rent", doc.rent, "sales_invoice_status", doc.status, update_modified=False
        )


def on_cancel(doc, method):
    try:
        rent_name = doc.flags.get("c4rent_rent_name") or doc.get("rent")
        related_stock_entries = doc.flags.get("c4rent_related_stock_entries") or []

        _wipe_links_on_stock_entries(related_stock_entries)
        if doc.meta.has_field("stock_entry"):
            frappe.db.set_value(
                "Sales Invoice", doc.name, "stock_entry", None, update_modified=False
            )
        _unlink_rent_references_for_cancelled_invoice(
            rent_name=rent_name,
            sales_invoice_name=doc.name,
            related_stock_entries=related_stock_entries,
        )
        _sync_rent_status(rent_name)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Sales Invoice Cancel Error")
        raise


def update_rent_status(rent_doc, sales_invoice_doc):
    """Recompute Rent status and pointers based on submitted Sales Invoices."""
    _sync_rent_status(rent_doc.name, preferred_sales_invoice=sales_invoice_doc.name)


def create_stock_entry(doc):
    """Create and submit Stock Entry linked to the submitted Sales Invoice."""
    new_doc = frappe.get_doc(
        {
            "doctype": "Stock Entry",
            "transaction_date": doc.posting_date,
            "stock_entry_type": "Material Transfer",
            "customer": doc.customer,
            "rent": doc.rent,
            "from_warehouse": doc.from_warehouse,
            "to_warehouse": doc.to_warehouse,
            "sales_invoice": doc.name,
        }
    )

    for item in doc.items:
        new_item = new_doc.append("items", {})
        new_item.item_code = item.item_code
        new_item.item_name = item.item_name
        new_item.qty = item.rent_qty
        new_item.s_warehouse = doc.from_warehouse
        new_item.t_warehouse = doc.to_warehouse
        new_item.customer = doc.customer
        new_item.cost_center = doc.cost_center

    new_doc.insert(ignore_permissions=True)
    new_doc.submit()

    if doc.meta.has_field("stock_entry"):
        frappe.db.set_value(
            "Sales Invoice", doc.name, "stock_entry", new_doc.name, update_modified=False
        )


@frappe.whitelist()
def cancel_sales_invoice_with_unlink(sales_invoice_name, rent_name=None):
    """Cancel Sales Invoice through the standard workflow hooks."""
    sales_invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice_name)

    if sales_invoice_doc.docstatus == 2:
        return _("Sales Invoice {0} is already cancelled.").format(sales_invoice_name)

    if sales_invoice_doc.docstatus != 1:
        frappe.throw(_("Only submitted Sales Invoice can be cancelled."))

    sales_invoice_doc.cancel()
    _sync_rent_status(rent_name or sales_invoice_doc.get("rent"))

    return _(
        "Successfully cancelled Sales Invoice {0}, cancelled related Stock Entries, and updated Rent status."
    ).format(sales_invoice_name)


@frappe.whitelist()
def unlink_all_before_cancel(sales_invoice_name, rent_name):
    """Legacy helper: unlink references for the selected Sales Invoice only."""
    try:
        if rent_name:
            frappe.db.set_value(
                "Rent",
                rent_name,
                {"sales_invoice": None, "sales_invoice_status": None, "stock_entry": None},
                update_modified=False,
            )

        stock_entries = _get_related_submitted_stock_entries(sales_invoice_name)
        _wipe_links_on_stock_entries(stock_entries)

        frappe.db.set_value(
            "Sales Invoice",
            sales_invoice_name,
            {"rent": None, "stock_entry": None},
            update_modified=False,
        )

        return _(
            "Successfully unlinked all references. You can now cancel the Sales Invoice."
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Unlink Before Cancel Error")
        raise


@frappe.whitelist()
def unlink_stock_entries_from_rent(sales_invoice_name):
    """Legacy helper: unlink related Stock Entries from Rent/Sales Invoice references."""
    stock_entries = _get_related_submitted_stock_entries(sales_invoice_name)
    _wipe_links_on_stock_entries(stock_entries)
    return _("Unlinked {0} Stock Entries for Sales Invoice {1}.").format(
        len(stock_entries), sales_invoice_name
    )
