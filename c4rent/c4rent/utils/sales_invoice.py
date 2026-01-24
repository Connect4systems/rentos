import frappe
from frappe import _
from frappe.utils import flt
import json

@frappe.whitelist()
def get_remaining_quantities(rent):
    # الحصول على الكميات الأصلية
    rent_details = frappe.get_all('Rent Detail',
        filters={'parent': rent},
        fields=['name', 'item_code', 'item_name', 'rate', 'uom', 'qty', 'return_qty'])
    
    # حساب الكميات المسلمة
    delivered_items = frappe.db.sql("""
        SELECT item_code, SUM(rent_qty) as total_qty
        FROM `tabSales Invoice Item`
        WHERE rent_detail IN %(rent_details)s
        AND docstatus = 1
        GROUP BY item_code
    """, {'rent_details': [d.name for d in rent_details]}, as_dict=1)
    
    delivered_map = {d.item_code: d.total_qty for d in delivered_items}
    
    # حساب الكميات المتبقية
    remaining_items = []
    for d in rent_details:
        delivered = flt(delivered_map.get(d.item_code, 0))
        remaining = flt(d.qty) - flt(d.return_qty) - delivered
        
        if remaining > 0:
            remaining_items.append({
                'name': d.name,
                'item_code': d.item_code,
                'item_name': d.item_name,
                'rate': d.rate,
                'uom': d.uom,
                'remaining_qty': remaining
            })
    
    return {'remaining_items': remaining_items}

@frappe.whitelist()
def validate_quantities(rent, items):
    items = json.loads(items)  # Parse the JSON string into a list of dictionaries
    remaining = get_remaining_quantities(rent)
    remaining_map = {d['item_code']: d['remaining_qty'] for d in remaining['remaining_items']}

    # Get available item codes
    available_item_codes = set(remaining_map.keys())

    for item in items:
        item_code = item['item_code']
        requested = flt(item.get('qty'))
        if item.get('selling_price_list') == "Daily":
            requested = flt(item.get('rent_qty')) * flt(item.get('days'))

        # Check if the item exists in the available items
        if item_code not in available_item_codes:
            frappe.msgprint(_(f"الصنف {item_code} غير متاح للإيجار."))
            return {'is_valid': False}
            
        if requested > remaining_map.get(item_code, 0):
            # frappe.msgprint(_(f"الكمية المطلوبة لـ {item_code} تتجاوز الكمية المتبقية"))
            return {'is_valid': False}

    return {'is_valid': True}