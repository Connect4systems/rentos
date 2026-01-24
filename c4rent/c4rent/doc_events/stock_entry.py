import frappe
from frappe import _


def before_save(doc, method):
    """
    Before saving a Stock Entry, ensure that each item in the items child table
    inherits the source warehouse (s_warehouse) and target warehouse (t_warehouse)
    from the parent document's from_warehouse and to_warehouse fields.
    
    Args:
        doc (frappe.Document): Stock Entry document
        method (str): Hook method name
    """
    # Set s_warehouse and t_warehouse for each item if not already set
    for item in doc.items:
        # Set source warehouse from parent's from_warehouse if not already set
        if doc.from_warehouse and not item.s_warehouse:
            item.s_warehouse = doc.from_warehouse
        
        # Set target warehouse from parent's to_warehouse if not already set
        if doc.to_warehouse and not item.t_warehouse:
            item.t_warehouse = doc.to_warehouse


def before_insert(doc, method):
    """
    Before inserting a new Stock Entry, ensure that each item in the items child table
    inherits the source warehouse (s_warehouse) and target warehouse (t_warehouse)
    from the parent document's from_warehouse and to_warehouse fields.
    
    Args:
        doc (frappe.Document): Stock Entry document
        method (str): Hook method name
    """
    # Set s_warehouse and t_warehouse for each item
    for item in doc.items:
        # Set source warehouse from parent's from_warehouse if not already set
        if doc.from_warehouse and not item.s_warehouse:
            item.s_warehouse = doc.from_warehouse
        
        # Set target warehouse from parent's to_warehouse if not already set
        if doc.to_warehouse and not item.t_warehouse:
            item.t_warehouse = doc.to_warehouse
