# -*- coding: utf-8 -*-
{
    'name': 'Turkish POS Abstract Payment',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Payment',
    'summary': 'Abstract payment method module with modern Odoo 19 POS integration',
    'description': """
Turkish POS Abstract Payment Module
====================================
Extensible abstract payment infrastructure for Turkish POS with:
- Abstract payment method model for easy extension
- Concrete payment methods (Cash, Credit Card, Bank Transfer)
- Multi-currency support (TRY, USD, EUR)
- BIN-based installment detection
- Modern Odoo 19 _processDirectFlow integration
- 3D Secure payment flow (initiate -> 3D -> callback -> complete)
- Gateway credential management
- Category-based installment limits with inheritance
- Product-level installment options
- Null-guarded frontend JavaScript
- Turkish language support
- Test data and documentation
    """,
    'author': 'Turkish POS Team',
    'website': 'https://github.com/preamae/odoo19-turkish-pos-main',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'payment',
        'website_sale',
        'product',
        'sale',
        'web',
        'turkish_pos',  # Required for turkish.pos.bank and turkish.pos.bin models
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        
        # Views
        'views/abstract_payment_method_views.xml',
        'views/payment_method_views.xml',
        'views/templates.xml',
        
        # Data
        'data/abstract_payment_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'turkish_pos_abstract_payment/static/src/css/payment_abstract.css',
            'turkish_pos_abstract_payment/static/src/js/abstract_payment_form.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
