# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


# =============================================================================
# PAYMENT METHOD EXAMPLES AND DOCUMENTATION
# =============================================================================
#
# This file previously contained example model classes (PaymentMethodCash,
# PaymentMethodCreditCard, PaymentMethodBankTransfer) that inherited from
# payment.method. These have been REMOVED because:
#
# 1. They caused Many2many field conflicts (all inherited turkish_pos_bank_ids
#    field with the same relation table)
# 2. They are not needed - payment methods should be created as records of
#    payment.method model, not as separate model classes
# 3. The data file (abstract_payment_data.xml) already creates the necessary
#    payment method records
#
# HOW TO CREATE PAYMENT METHODS:
# ===============================
#
# Method 1: Via Data Files (Recommended)
# ---------------------------------------
# Create records in abstract_payment_data.xml:
#
#   <record id="payment_method_cash" model="payment.method">
#       <field name="name">Cash Payment</field>
#       <field name="code">cash</field>
#       <field name="payment_type">cash</field>
#       ...
#   </record>
#
# Method 2: Via Python Code
# --------------------------
# Use the helper function below or create directly:
#
#   cash_method = env['payment.method'].create({
#       'name': 'Cash Payment',
#       'code': 'cash',
#       'payment_type': 'cash',
#       ...
#   })
#
# Method 3: Via Odoo UI
# ---------------------
# Navigate to: Abstract Payment > Payment Methods > Create
#
# =============================================================================


# =============================================================================
# TEST DATA HELPER
# =============================================================================

def create_test_payment_methods(env):
    """Create test payment methods for demo/testing purposes.
    
    This function can be called from data files or manually to create
    sample payment methods for testing the module.
    
    Args:
        env: Odoo environment
        
    Returns:
        dict: Created payment method records
    """
    
    # Get currencies
    Currency = env['res.currency'].sudo()
    try_currency = Currency.search([('name', '=', 'TRY')], limit=1)
    usd_currency = Currency.search([('name', '=', 'USD')], limit=1)
    eur_currency = Currency.search([('name', '=', 'EUR')], limit=1)
    
    currencies = try_currency | usd_currency | eur_currency
    
    # 1. Cash Payment Method
    cash_method = env['payment.method'].create({
        'name': 'Nakit Ödeme',
        'code': 'cash',
        'payment_type': 'cash',
        'sequence': 10,
        'description': 'Nakit ödeme yöntemi - Teslimat sırasında nakit ödeme',
        'supported_currency_ids': [(6, 0, currencies.ids)],
        'min_amount': 0.0,
        'max_amount': 10000.0,
        'supports_installments': False,
        'requires_3d_secure': False,
        'show_on_checkout': True,
        'turkish_pos_enabled': False,
    })
    
    _logger.info("Created test cash payment method: %s", cash_method.name)
    
    # 2. Credit Card Payment Method
    card_method = env['payment.method'].create({
        'name': 'Kredi Kartı',
        'code': 'credit_card',
        'payment_type': 'card',
        'sequence': 20,
        'description': 'Kredi kartı ile ödeme - Taksit seçenekleri mevcut',
        'supported_currency_ids': [(6, 0, currencies.ids)],
        'min_amount': 10.0,
        'max_amount': 0.0,  # No limit
        'supports_installments': True,
        'requires_3d_secure': True,
        'show_on_checkout': True,
        'turkish_pos_enabled': True,
        'max_installments': 12,
        'min_installment_amount': 100.0,
        'auto_capture': True,
        'allow_refund': True,
        'refund_policy': 'partial',
    })
    
    _logger.info("Created test credit card payment method: %s", card_method.name)
    
    # 3. Bank Transfer Payment Method
    transfer_method = env['payment.method'].create({
        'name': 'Banka Havalesi',
        'code': 'bank_transfer',
        'payment_type': 'bank_transfer',
        'sequence': 30,
        'description': 'Banka havalesi ile ödeme - EFT/Havale',
        'supported_currency_ids': [(6, 0, currencies.ids)],
        'min_amount': 100.0,
        'max_amount': 0.0,  # No limit
        'supports_installments': False,
        'requires_3d_secure': False,
        'show_on_checkout': True,
        'turkish_pos_enabled': False,
        'allow_refund': True,
        'refund_policy': 'full',
    })
    
    _logger.info("Created test bank transfer payment method: %s", transfer_method.name)
    
    return {
        'cash': cash_method,
        'credit_card': card_method,
        'bank_transfer': transfer_method,
    }
