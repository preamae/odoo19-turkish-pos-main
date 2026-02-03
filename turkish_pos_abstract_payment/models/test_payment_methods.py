# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class PaymentMethodCash(models.Model):
    """Cash Payment Method.
    
    Simple cash payment implementation for testing and demo purposes.
    No gateway integration required.
    """
    
    _name = 'payment.method.cash'
    _description = 'Cash Payment Method'
    _inherit = 'payment.method'
    _inherits = {}
    
    # This is a test/demo model - in production, you would configure
    # payment.method records via data files rather than creating separate models
    

class PaymentMethodCreditCard(models.Model):
    """Credit Card Payment Method.
    
    Credit card payment with installment and 3D Secure support.
    Integrates with Turkish POS banks for installment calculation.
    """
    
    _name = 'payment.method.credit.card'
    _description = 'Credit Card Payment Method'
    _inherit = 'payment.method'
    _inherits = {}
    
    # Additional card-specific fields
    accepted_card_types = fields.Selection(
        selection=[
            ('all', 'All Cards'),
            ('visa', 'Visa Only'),
            ('mastercard', 'Mastercard Only'),
            ('troy', 'Troy Only'),
        ],
        string='Accepted Card Types',
        default='all',
        help='Types of cards accepted by this payment method'
    )
    
    enable_bin_detection = fields.Boolean(
        string='Enable BIN Detection',
        default=True,
        help='Automatically detect bank from card BIN number'
    )
    
    # Override to set defaults for credit card
    @api.model
    def create(self, vals):
        """Set defaults for credit card payment method."""
        if 'payment_type' not in vals:
            vals['payment_type'] = 'card'
        if 'supports_installments' not in vals:
            vals['supports_installments'] = True
        if 'requires_3d_secure' not in vals:
            vals['requires_3d_secure'] = True
        return super().create(vals)


class PaymentMethodBankTransfer(models.Model):
    """Bank Transfer Payment Method.
    
    Bank transfer/wire payment method for larger transactions.
    Requires manual confirmation.
    """
    
    _name = 'payment.method.bank.transfer'
    _description = 'Bank Transfer Payment Method'
    _inherit = 'payment.method'
    _inherits = {}
    
    # Bank account details
    bank_account_number = fields.Char(
        string='Bank Account Number',
        help='Bank account number for receiving transfers'
    )
    
    iban = fields.Char(
        string='IBAN',
        help='International Bank Account Number'
    )
    
    swift_code = fields.Char(
        string='SWIFT/BIC Code',
        help='Bank SWIFT/BIC code'
    )
    
    bank_name = fields.Char(
        string='Bank Name',
        help='Name of the bank'
    )
    
    bank_branch = fields.Char(
        string='Bank Branch',
        help='Bank branch information'
    )
    
    account_holder = fields.Char(
        string='Account Holder',
        help='Name of the account holder'
    )
    
    transfer_instructions = fields.Text(
        string='Transfer Instructions',
        translate=True,
        help='Instructions for customers on how to make the bank transfer'
    )
    
    confirmation_required = fields.Boolean(
        string='Confirmation Required',
        default=True,
        help='Payment must be manually confirmed after transfer'
    )
    
    auto_confirm_after_days = fields.Integer(
        string='Auto-Confirm After Days',
        default=0,
        help='Automatically confirm payment after N days (0 = disabled)'
    )
    
    # Override to set defaults for bank transfer
    @api.model
    def create(self, vals):
        """Set defaults for bank transfer payment method."""
        if 'payment_type' not in vals:
            vals['payment_type'] = 'bank_transfer'
        if 'supports_installments' not in vals:
            vals['supports_installments'] = False
        if 'requires_3d_secure' not in vals:
            vals['requires_3d_secure'] = False
        return super().create(vals)
    
    def get_transfer_details(self):
        """Get formatted bank transfer details for customer.
        
        Returns:
            dict: Bank transfer information
        """
        self.ensure_one()
        
        return {
            'bank_name': self.bank_name,
            'account_holder': self.account_holder,
            'account_number': self.bank_account_number,
            'iban': self.iban,
            'swift': self.swift_code,
            'branch': self.bank_branch,
            'instructions': self.transfer_instructions,
        }


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
