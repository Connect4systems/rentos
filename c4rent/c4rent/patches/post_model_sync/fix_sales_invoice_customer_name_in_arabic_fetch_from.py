import frappe


def execute():
    custom_field_name = "Sales Invoice-customer_name_in_arabic"

    if not frappe.db.exists("Custom Field", custom_field_name):
        return

    customer_meta = frappe.get_meta("Customer")
    fetch_from_source = (
        "customer.customer_name_in_arabic"
        if customer_meta.has_field("customer_name_in_arabic")
        else "customer.customer_name"
    )

    current_fetch_from = frappe.db.get_value("Custom Field", custom_field_name, "fetch_from")
    if current_fetch_from != fetch_from_source:
        frappe.db.set_value(
            "Custom Field",
            custom_field_name,
            "fetch_from",
            fetch_from_source,
            update_modified=False,
        )
        frappe.clear_cache(doctype="Sales Invoice")
