import frappe


def execute():
    obsolete_fields = [
        "custom_rent_item_group",
        "custom_rent_letter_head",
        "custom_rent_print_heading",
        "custom_rent_income_account",
    ]

    for fieldname in obsolete_fields:
        custom_field_name = f"POS Profile-{fieldname}"
        if frappe.db.exists("Custom Field", custom_field_name):
            frappe.delete_doc("Custom Field", custom_field_name, force=1, ignore_permissions=True)

    frappe.clear_cache(doctype="POS Profile")
