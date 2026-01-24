// Copyright (c) 2023, Connect 4 Systems and contributors
// For license information, please see license.txt

frappe.ui.form.on('Rent', {
    refresh: function(frm) {
        if (frm.doc.docstatus != 1) {
            initialize_slider(frm);
            if (frm.doc.item_group) {
                load_items(frm, frm.doc.item_group);
            }
        }

    },
    item_group: function(frm) {
        load_items(frm,frm.doc.item_group); // Load items based on the selected item group
    },
    onload: function (frm) {
        update_sales_invoice_status(frm);
        // استخدام دالة غير متزامنة لجلب القيمة
        frappe.db.get_single_value('Rent Settings', 'default_target_warehouse')
            .then(defaultTargetWarehouse => {
                if (defaultTargetWarehouse) {
                    // التأكد من وجود المستودع قبل التعيين
                    frappe.db.exists('Warehouse', defaultTargetWarehouse)
                        .then(exists => {
                            if (exists) {
                                frm.set_value("target_warehouse", defaultTargetWarehouse);
                            } else {
                                frappe.msgprint({
                                    title: __("مستودع غير موجود"),
                                    indicator: "red",
                                    message: __("المستودع المحدد في الإعدادات غير موجود: {0}", [defaultTargetWarehouse])
                                });
                            }
                        });
                } else {
                    frappe.msgprint({
                        title: __("إعدادات ناقصة"),
                        indicator: "red",
                        message: __("يجب تعبئة حقل 'Default Target Warehouse' في إعدادات التأجير أولاً")
                    });
                }
            });
        initialize_slider(frm);
        if (frm.doc.item_group) {
            load_items(frm, frm.doc.item_group);
        }
        setTimeout(() => {
          const stockEntryButton = document.querySelector('.document-link[data-doctype="Stock Entry"] .btn-new');
          if (stockEntryButton) {
              stockEntryButton.style.display = 'none';
            }
        }, 500);   
        setTimeout(() => {
            const paymentEntryButton = document.querySelector('.document-link[data-doctype="Payment Entry"] .btn-new');
            if (paymentEntryButton) {
                paymentEntryButton.style.display = 'none';
              }
          }, 500);       
          setTimeout(() => {
            const salesInvoiceButton = document.querySelector('.document-link[data-doctype="Sales Invoice"] .btn-new');
            if (salesInvoiceButton) {
                salesInvoiceButton.style.display = 'none';
              }
          }, 500);                 
    },
});

frappe.ui.form.on("Rent", {
    refresh: function(frm, cdt, cdn) {
        if (frm.doc.docstatus == 1) {
            if (frm.doc.status === "Returned") {
                // Disable the button and show a message
                // frm.disable_save(); // Prevents accidental saving while disabled
                frm.add_custom_button(__("Sales Invoice"), function() {
                    frappe.throw(__("This Rent document has been fully returned. Creating a Sales Invoice is not possible."));
                }, __("Create")).addClass("btn-disabled"); // Add a class to visually disable the button
            } else {
                // Enable the button if the status is not "Returned"
                frm.enable_save(); // Re-enable saving
                frm.add_custom_button(__("Sales Invoice"), function() {
                    frappe.route_options = {
                        "rent": frm.doc.name,
                        "customer": frm.doc.customer,
                        "branch": frm.doc.branch,
                        "cost_center": frm.doc.cost_center,
                        "from_warehouse": frm.doc.target_warehouse,
                        "to_warehouse": frm.doc.source_warehouse,
                        "selling_price_list": "Daily",
                        "cost_center": frm.doc.cost_center,
                    };
                    frappe.new_doc("Sales Invoice");
                }, __("Create"));
            }
            // Add the Payment Entry button
            frm.add_custom_button(__("Payment Entry"), function() {
                frm.events.make_payment_entry(frm)
            }, __("Create"));            
        }
    },
    make_payment_entry: function(frm) {
		frappe.model.open_mapped_doc({
			method: "c4rent.c4rent.doctype.rent.rent.make_payment_entry",
			frm: frm
		});
	},
});
frappe.ui.form.on("Rent", "validate", function() {
    for (var i = 0; i < cur_frm.doc.time_logs.length; i++) {
        cur_frm.doc.time_logs[i].uom = cur_frm.doc.rent_type;
    }
    cur_frm.refresh_field('time_logs');
});

frappe.ui.form.on("Rent Detail", "rate", function(frm, doctype, name) {
    let row = locals[doctype][name];
    row.amount = row.rate * row.qty; 
    refresh_field("time_logs");
});

frappe.ui.form.on("Rent", "validate", function(frm, cdt, cdn) {
    $.each(frm.doc.time_logs || [], function(i, d) {
        d.source_warehouse = frm.doc.source_warehouse;
    });
    cur_frm.refresh_field('time_logs');
});

// Modified the following 'item_code' event to correctly update the rate field in the 'Rent Detail' table.
frappe.ui.form.on("Rent Detail", "item_code", function(frm, cdt, cdn) {
    const row = locals[cdt][cdn]; // Get current row
    const priceList = cur_frm.doc.rent_type == "Daily" ? "Daily" : "Monthly";

    if (row.item_code) {
        frappe.call({
            'method': 'frappe.client.get_value',
            'args': {
                'doctype': 'Item Price',
                'fieldname': 'price_list_rate',
                'filters': {
                    'item_code': row.item_code,
                    "price_list": priceList
                }
            },
            callback: function(r) {
                if (r.message) {
                    frappe.model.set_value(cdt, cdn, 'rate', r.message.price_list_rate); // Set the rate
                    frappe.model.set_value(cdt, cdn, 'amount', r.message.price_list_rate * row.qty); // Calculate and set amount
                } else {
                    frappe.model.set_value(cdt, cdn, 'rate', 0); // Set rate to 0 if no price found
                    frappe.model.set_value(cdt, cdn, 'amount', 0); // Set amount to 0 if no price found
                }
                cur_frm.refresh_field('time_logs');
            }
        });
    }
});
function update_sales_invoice_status(frm) {
    if (frm.doc.sales_invoice) {
        // جلب حالة الفاتورة باستخدام Promise
        frappe.db.get_value('Sales Invoice', 
            frm.doc.sales_invoice, 
            'status'
        ).then(r => {
            if (r.message && r.message.status) {
                frm.set_value('sales_invoice_status', r.message.status);
                frm.refresh_field('sales_invoice_status');
            }
        }).catch(() => {
            console.error('Error fetching invoice status');
        });
    } else {
        frm.set_value('sales_invoice_status', 'غير مرتبط بفاتورة');
        frm.refresh_field('sales_invoice_status');
    }
}
//----------------------------------------------------------------------------------
// سلايدر مجموعات الأصناف
//----------------------------------------------------------------------------------
function initialize_slider(frm) {
    let html_field = frm.get_field('item_group_html');
    if (!html_field || html_field.slider_initialized) return;

    html_field.slider_initialized = true;

    if (!html_field.$wrapper.find('.swiper-container').length) {
        html_field.$wrapper.html(`
            <div class="swiper-container">
                <div class="swiper-wrapper" id="item_group-container"></div>
                <div class="swiper-button-next"></div>
                <div class="swiper-button-prev"></div>
                <div class="swiper-pagination"></div>
            </div>
        `);
    }

    load_item_group(frm);
}

function load_item_group(frm) {
    frappe.call({
        doc: frm.doc,
        method: "get_item_group",
        callback: function(r) {
            if (r.message) {
                const container = frm.get_field('item_group_html').$wrapper.find('#item_group-container');
                container.empty();

                if (frm.doc.docstatus === 1) {
                    const selected_item_group = frm.doc.item_group;
                    if (!selected_item_group) {
                        container.html("<p>لم يتم اختيار مجموعة الاصناف.</p>");
                        return;
                    }

                    frappe.call({
                        doc: frm.doc,
                        method: "get_item_group_details",
                        args: {
                            item_group: selected_item_group
                        },
                        callback: function(res) {
                            if (res.message) {
                                let ig = res.message;
                                let image_src = ig.image ? frappe.utils.get_file_link(ig.image) : '/assets/your_app/images/default.png';

                                const slide = `
                                    <div class="swiper-slide">
                                        <div class="card">
                                            <img src="${image_src}" class="card-img-top fixed-image select_item_group_image" data-item_group="${ig.name}" alt="${ig.name}" style="width: 100%; object-fit: contain; cursor: pointer;">
                                            <div class="card-body">
                                                <h5 class="card-title">${ig.name}</h5>

                                            </div>
                                        </div>
                                    </div>
                                `;
                                container.append(slide);
                                initialize_swiper(frm, true);
                            } else {
                                container.html("<p>مجموعة الاصناف المختارة غير موجودة.</p>");
                            }
                        }
                    });
                } else {
                    if (r.message.length === 0) {
                        container.html("<p>لا توجد مجموعة اصناف متاحة.</p>");
                        return;
                    }

                    r.message.forEach(ig => {
                        let image_src = ig.image ? frappe.utils.get_file_link(ig.image) : '/assets/your_app/images/default.png';

                        const slide = `
                            <div class="swiper-slide">
                                <div class="card">
                                    <img src="${image_src}" class="card-img-top fixed-image select_item_group_image" data-item_group="${ig.name}" alt="${ig.name}" style="width: 100%; object-fit: contain; cursor: pointer;">
                                    <div class="card-body">
                                        <h5 class="card-title">${ig.name}</h5>

                                    </div>
                                </div>
                            </div>
                        `;
                        container.append(slide);
                    });

                    initialize_swiper(frm, false);
                }
            } else {
                frappe.msgprint(__("لم يتم العثور على مجموعة الاصناف لعرضها."));
            }
        }
    });
}

function initialize_swiper(frm, read_only) {
    const html_field = frm.get_field('item_group_html');
    let swiperElement = html_field.$wrapper.find('.swiper-container')[0];

    if (html_field.swiper_instance) {
        html_field.swiper_instance.destroy(true, true);
    }

    html_field.swiper_instance = new Swiper(swiperElement, {
        slidesPerView: 1,
        spaceBetween: 5,
        loop: false,
        pagination: {
            el: html_field.$wrapper.find('.swiper-pagination')[0],
            clickable: true,
        },
        navigation: {
            nextEl: html_field.$wrapper.find('.swiper-button-next')[0],
            prevEl: html_field.$wrapper.find('.swiper-button-prev')[0],
            enabled: !read_only
        },
        keyboard: {
            enabled: !read_only,
            onlyInViewport: true,
        },
        mousewheel: {
            invert: false,
            enabled: !read_only,
        },
        // width: html_field.$wrapper.find('.swiper-container').width(),
		breakpoints: {
            320: {slidesPerView: 1,},
            450: {slidesPerView: 2,},
            480: {slidesPerView: 3,},
            640: {slidesPerView: 4,},
            992: {slidesPerView: 5,},
            1300: {slidesPerView: 6,},
            1600: {slidesPerView: 7,}            
        }
    });
    html_field.$wrapper.find('.select_item_group_image').on('click', function() {
        const itemGroupName = $(this).data('item_group');
        if (itemGroupName) {
            frm.set_value('item_group', itemGroupName);

            frm.save().then(() => {
                load_item_group(frm);
                load_items(frm, itemGroupName); // Load items after selecting an item group
            }).catch(err => {
                console.error("خطأ في حفظ المستند: ", err);
                frappe.msgprint(__("حدث خطأ أثناء حفظ المستند."));
            });
        } else {
            console.error("لا يوجد قيمة لاسم مجموعة الأصناف");
        }
    });
    if (read_only) {
        html_field.$wrapper.find('.swiper-button-next, .swiper-button-prev').hide();
    } else {
        html_field.$wrapper.find('.selected_item_group').remove();
    }

    if (!document.getElementById('slider-styles')) {
        let style = document.createElement('style');
        style.id = 'slider-styles';
        style.innerHTML = `
        /* Default Slider Styles (Applied to all screen sizes) */
        .card {
            width: 100%;
            max-width: 180px;
            height: auto;
            min-height: auto;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
            transition: transform 0.2s, box-shadow 0.2s;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            background-color: #fff;
            margin: 5px; /* Add some margin between cards */
            box-sizing: border-box; /* Important: Include padding/border in width */
        }

        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        .card img.fixed-image {
            width: 100%;
            height: 90px;
            object-fit: contain;
            border-bottom: 1px solid #E0E0E0;
            object-position: center;
        }

        .card-body {
            padding: 6px;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            text-align: center;
            height: auto;
        }

        .card-title {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 0.8rem;
            color: #333;
            margin-bottom: 2px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .card-text {
            font-size: 0.75rem;
            color: #666;
            flex-grow: 1;
        }

        .selected_item_group {
            width: 80%;
            margin-top: 8px;
            background-color: #7E546F;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 12px;
            transition: background-color 0.3s;
            font-weight: 500;
            cursor: pointer;
            font-size: 0.9rem;
            outline: none;
        }

        .selected_item_group:hover {
            background-color: #388E3C;
        }

        .swiper-container {
            width: 100%;
            overflow: hidden;
            padding-top: 2px;
            padding-bottom: 2px;
        }

        .swiper-pagination {
            margin-top: 8px;
            position: relative;
            z-index: 1;
        }

        .swiper-slide {
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 5px; /* Add padding to the slides */
            box-sizing: border-box; /*  Include padding and border */
        }

        .swiper-button-next,
        .swiper-button-prev {
            color: #7E546F;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            transition: all 0.3s;
        }

        .swiper-button-next:hover,
        .swiper-button-prev:hover {
            color: #7E546F;
        }

        .swiper-pagination-bullet {
            background: rgb(236, 209, 227);
            opacity: 1;
        }

        .swiper-pagination-bullet-active {
            background: #7E546F;
        }

        /*  Media Queries for Responsive Design */
        @media (max-width: 1200px) {
            .card {
                max-width: 28%; /* Slightly more space */
                margin: 3px;  /* Reduce margin a bit */
            }
        }

        @media (max-width: 992px) {
            .card {
                max-width: 45%; /*  Two cards per row */
                margin: 3px;
            }
        }

        @media (max-width: 768px) {
            .card {
                max-width: 48%; /*  Allow for spacing between cards */
                margin: 2px; /* Even smaller margins */
            }

            .card img.fixed-image {
                height: 75px; /* Slightly smaller image */
            }

            .card-title {
                font-size: 0.7rem; /* Smaller text */
            }
        }

        @media (max-width: 576px) {
            .card {
                max-width: 95%; /* Almost full width */
                margin: 5px auto; /* Center and add some top/bottom margin */
            }

            .card img.fixed-image {
                height: 90px; /*  Increase image height on mobile */
            }

            .card-title {
                font-size: 0.8rem;
            }

            .swiper-container {
                padding: 0 5px; /* Keep some padding */
            }
        }

        /* Landscape Orientation Adjustments (Optional) */
        @media (orientation: landscape) and (max-height: 480px) {
            .card img.fixed-image {
                height: 60px; /* Smaller images in landscape on small screens */
            }

            .card-title {
                font-size: 0.65rem;
            }
        }

        `;
        document.head.appendChild(style);
    }
}

//----------------------------------------------------------------------------------
// سلايدر الأصناف
//----------------------------------------------------------------------------------
function load_items(frm, item_group) {
    if (!item_group) return;

    frappe.call({
        doc: frm.doc,
        method: "get_items",
        args: { item_group: item_group },
        callback: function(response) {
            const items = response.message;
            const container = frm.get_field('item_html').$wrapper;

            // إعداد بنية HTML للسلايدر
            container.html(`
                <div class="swiper-container">
                    <div class="swiper-wrapper" id="item-container"></div>
                    <div class="swiper-button-next"></div>
                    <div class="swiper-button-prev"></div>
                    <div class="swiper-pagination"></div>
                </div>
            `);

            const itemContainer = container.find('#item-container');

            if (items && items.length) {
                items.forEach(function(item) {
                    const slide = `
                    <div class="swiper-slide">
                        <div class="card">
                            <img src="${item.image || '/assets/your_app/images/default.png'}" class="card-img-top fixed-image select_item_image" data-item_code="${item.name}" alt="${item.item_name}" style="width: 100%; object-fit: contain; cursor: pointer;">
                            <div class="card-body">
                                <h5 class="card-title">${item.item_name}</h5>

                            </div>
                        </div>
                    </div>
                `;
                    itemContainer.append(slide);
                });

                // تهيئة سلايدر العناصر
                initialize_item_slider(frm ,container);
            } else {
                itemContainer.html("<p>لا توجد عناصر مرتبطة بمجموعة الأصناف المختارة.</p>");
            }
        },
        error: function(error) {
            console.error("Error loading items: ", error);
            frm.get_field('item_html').$wrapper.html("<p>حدث خطأ أثناء جلب العناصر.</p>");
        }
    });
}
// تهيئة سلايدر العناصر
function initialize_item_slider(frm, container) {
    const swiperContainer = container.find('.swiper-container')[0];

    const swiper = new Swiper(swiperContainer, {
        slidesPerView: 1,
        spaceBetween: 5,
        loop: false,
        pagination: {
            el: container.find('.swiper-pagination')[0],
            clickable: true,
        },
        navigation: {
            nextEl: container.find('.swiper-button-next')[0],
            prevEl: container.find('.swiper-button-prev')[0],
        },
		breakpoints: {
            320: {slidesPerView: 1,},
            450: {slidesPerView: 2,},
            480: {slidesPerView: 3,},
            640: {slidesPerView: 4,},
            992: {slidesPerView: 5,},
            1300: {slidesPerView: 6,},
            1600: {slidesPerView: 7,}            
        }
    });

    container.find('.select_item_image').on('click', (function(current_frm) { // Create a closure
        return function() {
            const itemCode = $(this).data('item_code');

            if (itemCode) {
                add_item_to_table(current_frm, itemCode); // Use the captured 'current_frm'
            }
        };
    })(frm));

    container.find('.select_item').remove();
}

//----------------------------------------------------------------------------------
// Add item to sub-table
//----------------------------------------------------------------------------------
function add_item_to_table(frm, item_code) {
    const priceList = frm.doc.rent_type === "Daily" ? "Daily" : "Monthly";
    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Item',
            name: item_code
        },
        callback: function(item_response) {
            const item_details = item_response.message;

            if (item_details) {
                frappe.call({
                    method: 'frappe.client.get_value',
                    args: {
                        doctype: 'Item Price',
                        filters: {
                            item_code: item_details.name,
                            price_list: priceList
                        },
                        fieldname: 'price_list_rate'
                    },
                    callback: function(price_response) {
                        // Handle null/undefined price_list_rate
                        const price = (price_response.message && price_response.message.price_list_rate) ? price_response.message.price_list_rate : 0;

                        let item_found = false;
                        let row_name = null;

                        // Check existing items
                        for (let i = 0; i < frm.doc.time_logs.length; i++) {
                            const log = frm.doc.time_logs[i];
                            if (log.item_code === item_details.name) {
                                item_found = true;
                                row_name = log.name;
                                break;
                            }
                        }

                        if (item_found && row_name) {
                            // Update existing row
                            const current_qty = frappe.model.get_value('Rent Detail', row_name, 'qty');
                            const new_qty = current_qty + 1;
                            frappe.model.set_value('Rent Detail', row_name, 'qty', new_qty);
                            frappe.model.set_value('Rent Detail', row_name, 'amount', new_qty * price);
                        } else {
                            // Add new row with validated rate
                            const new_row = frm.add_child('time_logs');
                            new_row.item_code = item_details.name;
                            new_row.item_name = item_details.item_name;
                            new_row.rate = price;
                            new_row.qty = 1;
                            new_row.amount = new_row.qty * new_row.rate;
                        }

                        frm.refresh_field('time_logs');
                        frm.save_or_update().then(() => {
                            frappe.msgprint(__('تم حفظ التغييرات بنجاح.'));
                        }).catch(err => {
                            frappe.msgprint(__('حدث خطأ أثناء حفظ التغييرات.'));
                        });
                    },
                    error: function(err) {
                        console.error("Error fetching item price: ", err);
                        frappe.msgprint(__('Could not fetch item price.'));
                    }
                });
            } else {
                frappe.msgprint(__('Item not found or invalid item code.'));
            }
        },
        error: function(err) {
            console.error("Error fetching item details: ", err);
            frappe.msgprint(__('Could not fetch item details.'));
        }
    });
}