frappe.ui.form.on("Sales Invoice", {
    onload: async function(frm) {
        if (frm.doc.__islocal && frm.doc.rent) {
            const isDailyRent = await is_daily_rent_invoice(frm);
            if (isDailyRent) {
                check_remaining_quantities(frm);
            }
        }
        
        // Add button on load for submitted documents
        if (frm.doc.docstatus === 1 && frm.doc.rent) {
            add_unlink_cancel_button(frm);
        }

    },
    
    after_save: function(frm) {
        // Add button after save for submitted documents
        if (frm.doc.docstatus === 1 && frm.doc.rent) {
            add_unlink_cancel_button(frm);
        }
    },
    
    validate: function(frm) {
        validate_remaining_quantities(frm);
    }
});

const get_linked_rent_data = async (frm) => {
    if (!frm.doc.rent) {
        return null;
    }

    if (frm._linked_rent_data && frm._linked_rent_data.name === frm.doc.rent) {
        return frm._linked_rent_data;
    }

    const rentValue = await frappe.db.get_value('Rent', frm.doc.rent, ['rent_type', 'pos_profile']);
    const data = {
        name: frm.doc.rent,
        rent_type: rentValue.message ? rentValue.message.rent_type : null,
        pos_profile: rentValue.message ? rentValue.message.pos_profile : null
    };
    frm._linked_rent_data = data;
    return data;
};

const is_daily_rent_invoice = async (frm) => {
    const rentData = await get_linked_rent_data(frm);
    return !!(rentData && rentData.rent_type === 'Daily');
};

const get_rent_pos_profile = async (frm) => {
    if (frm.doc.pos_profile) {
        return frm.doc.pos_profile;
    }

    const rentData = await get_linked_rent_data(frm);
    const posProfile = rentData ? rentData.pos_profile : null;

    if (posProfile && !frm.doc.pos_profile) {
        await frm.set_value('pos_profile', posProfile);
    }

    return posProfile;
};

const get_pos_profile_income_account = async (frm) => {
    const posProfile = await get_rent_pos_profile(frm);
    if (!posProfile) {
        return null;
    }

    const profileValue = await frappe.db.get_value('POS Profile', posProfile, 'income_account');
    return profileValue.message ? profileValue.message.income_account : null;
};

const add_unlink_cancel_button = (frm) => {
    if (!frm.page.btn_unlink_cancel_added) {
        frm.add_custom_button(__('Unlink & Cancel'), function() {
            frappe.confirm(
                __('This will unlink Rent and Stock Entries, then cancel the Sales Invoice. Continue?'),
                function() {
                    frappe.call({
                        method: 'c4rent.c4rent.doc_events.sales_invoice.cancel_sales_invoice_with_unlink',
                        args: {
                            sales_invoice_name: frm.doc.name,
                            rent_name: frm.doc.rent
                        },
                        callback: function(r) {
                            if (r.message) {
                                frappe.msgprint({
                                    title: __('Success'),
                                    indicator: 'green',
                                    message: r.message
                                });
                                setTimeout(() => {
                                    location.reload();
                                }, 1500);
                            }
                        },
                        error: function(r) {
                            frappe.msgprint({
                                title: __('Error'),
                                indicator: 'red',
                                message: r.responseText || __('Failed to cancel Sales Invoice')
                            });
                        }
                    });
                }
            );
        }, __('Rent'));
        
        // Make button red/danger style
        frm.page.custom_actions.find('button:contains("Unlink & Cancel")').addClass('btn-danger');
        frm.page.btn_unlink_cancel_added = true;
    }
};

const check_remaining_quantities = (frm) => {
    frappe.call({
        method: 'c4rent.c4rent.utils.sales_invoice.get_remaining_quantities',
        args: { rent: frm.doc.rent },
        callback: (r) => {
            if(r.message.remaining_items.length === 0) {
                frappe.msgprint({
                    title: __('تحذير'),
                    message: __('تم إصدار جميع الكميات في فواتير سابقة'),
                    indicator: 'orange'
                });
                frm.doc.items = [];
                frm.refresh_field('items');
            }
            else if(frm.doc.__islocal) {
                fetch_items(frm, r.message.remaining_items);
            }
        }
    });
};

const fetch_items = async (frm, remaining_items) => {
    try {
        const incomeAccount = await get_pos_profile_income_account(frm);
        if (!incomeAccount) {
            frappe.msgprint({
                title: __("إعدادات ناقصة"),
                indicator: "red",
                message: __("Please set 'Income Account' in the selected POS Profile before continuing")
            });
            return;
        }

        const isDailyRent = await is_daily_rent_invoice(frm);
        frm.clear_table('items');

        remaining_items.forEach(item => {
            const row = frm.add_child('items');
            row.item_code = item.item_code;
            row.item_name = item.item_name;
            row.description = item.item_name;
            row.income_account = incomeAccount;
            row.rate = item.rate;
            row.uom = item.uom;
            row.rent_detail = item.name;
            row.rent_qty = item.remaining_qty;

            if (isDailyRent) {
                calculate_daily_quantities(frm, item, row);
            }
        });

        frm.refresh_field('items');
    } catch (error) {
        console.error('Error fetching POS Profile income account:', error);
    }
};

const calculate_daily_quantities = (frm, item, row) => {
    frappe.call({
        method: 'frappe.client.get_value',
        args: {
            doctype: 'Rent',
            fieldname: 'date',
            filters: { name: frm.doc.rent }
        },
        callback: (r) => {
            const start_date = new Date(r.message.date);
            const end_date = new Date(frm.doc.posting_date);
            const days = Math.ceil((end_date - start_date) / (1000 * 3600 * 24)) || 1;
            
            row.days = days;
            row.qty = item.remaining_qty * days;
            frm.refresh_field('items');
        }
    });
};

const validate_remaining_quantities = (frm) => {
    if(frm.doc.rent && frm.doc.items.length > 0) {
        frappe.call({
            method: 'c4rent.c4rent.utils.sales_invoice.validate_quantities',
            args: {
                rent: frm.doc.rent,
                items: frm.doc.items
            },
            callback: (r) => {
                if(!r.message.is_valid) {
                    // frappe.throw(__('الكميات المدخلة تتجاوز الكميات المتبقية'));
                }
            }
        });
    }
};

