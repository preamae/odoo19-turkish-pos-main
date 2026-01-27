# -*- coding: utf-8 -*-
{
    'name': 'Turkish Virtual POS (Sanal POS)',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Payment',
    'summary': 'Turkish bank virtual POS integration with installment support for eCommerce',
    'description': """
Turkish Virtual POS Payment Module
===================================
Supports Turkish payment gateways (Param, Tosla, iyzico, QNBPay)
with category-based installment limits, BIN detection, and 3D Secure.
    """,
    'author': 'Anirudha Talmale',
    'website': 'https://github.com/anirudhatalmale6-alt',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'payment',
        'product',
        'website_sale',
        'web',
    ],
    'data': [
        # 1. Security - must load first
        'security/ir.model.access.csv',

        # 2. Views (model extensions) - before data
        'views/payment_provider_views.xml',
        'views/gateway_views.xml',
        'views/bank_views.xml',
        'views/bin_views.xml',
        'views/installment_views.xml',
        'views/category_restriction_views.xml',
        'views/transaction_views.xml',
        'views/product_template_views.xml',
        'views/product_public_category_views.xml',
        'views/dashboard_views.xml',

        # 3. Data - after views
        'data/gateway_data.xml',
        'data/bank_data.xml',
        'data/bin_data.xml',
        'data/installment_data.xml',
        'data/provider_data.xml',

        # 4. Templates
        'views/templates.xml',
        'templates/product_installments.xml',
        'templates/payment_3d.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'turkish_pos/static/src/css/installment.css',
            'turkish_pos/static/src/css/payment_card.css',
            'turkish_pos/static/src/js/payment_installments.js',
        ],
    },
    'external_dependencies': {
        'python': [
            'requests',
            'zeep',
            'cryptography',
            'lxml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
