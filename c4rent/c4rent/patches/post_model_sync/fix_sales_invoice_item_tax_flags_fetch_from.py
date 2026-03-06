import frappe


def execute():
    custom_fields = {
        "Sales Invoice Item-is_zero_rated": "is_zero_rated",
        "Sales Invoice Item-is_exempt": "is_exempt",
    }

    item_meta = frappe.get_meta("Item")
    requires_cache_clear = False

    for custom_field_name, item_fieldname in custom_fields.items():
        if not frappe.db.exists("Custom Field", custom_field_name):
            continue

        fetch_from_source = (
            f"item_code.{item_fieldname}" if item_meta.has_field(item_fieldname) else None
        )
        current_fetch_from = frappe.db.get_value(
            "Custom Field", custom_field_name, "fetch_from"
        )

        if current_fetch_from != fetch_from_source:
            frappe.db.set_value(
                "Custom Field",
                custom_field_name,
                "fetch_from",
                fetch_from_source,
                update_modified=False,
            )
            requires_cache_clear = True

    if requires_cache_clear:
        frappe.clear_cache(doctype="Sales Invoice Item")
