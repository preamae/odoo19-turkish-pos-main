# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PaymentMethod(models.Model):
    """Concrete payment method model.
    
    This model extends payment.provider to add Turkish POS abstract payment capabilities.
    It provides the concrete implementation for various payment methods like
    cash, credit card, and bank transfer.
    """
    
    _name = 'payment.method'
    _description = 'Payment Method'
    _inherit = ['abstract.payment.method', 'mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'
    
    # Override code to make it unique
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Payment method code must be unique!'),
    ]
    
    # ========================================================================
    # ADDITIONAL FIELDS
    # ========================================================================
    
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        help='Company that owns this payment method'
    )
    
    # Turkish POS Integration
    turkish_pos_enabled = fields.Boolean(
        string='Enable Turkish POS',
        default=False,
        help='Enable Turkish POS integration features'
    )
    
    turkish_pos_bank_ids = fields.Many2many(
        comodel_name='turkish.pos.bank',
        relation='payment_method_turkish_pos_bank_rel',
        column1='method_id',
        column2='bank_id',
        string='Turkish POS Banks',
        help='Turkish banks available for this payment method'
    )
    
    # Installment Configuration
    max_installments = fields.Integer(
        string='Maximum Installments',
        default=12,
        help='Maximum number of installments allowed'
    )
    
    min_installment_amount = fields.Float(
        string='Minimum Installment Amount',
        default=100.0,
        digits=(12, 2),
        help='Minimum amount required per installment'
    )
    
    # Transaction Settings
    auto_capture = fields.Boolean(
        string='Auto Capture',
        default=True,
        help='Automatically capture payment after authorization'
    )
    
    allow_refund = fields.Boolean(
        string='Allow Refunds',
        default=True,
        help='Allow refunds for this payment method'
    )
    
    refund_policy = fields.Selection(
        selection=[
            ('full', 'Full Refund Only'),
            ('partial', 'Partial Refund Allowed'),
        ],
        string='Refund Policy',
        default='partial',
        help='Refund policy for this payment method'
    )
    
    # Display Options
    icon = fields.Binary(
        string='Icon',
        help='Icon image for this payment method'
    )
    
    show_on_checkout = fields.Boolean(
        string='Show on Checkout',
        default=True,
        help='Display this payment method on checkout page'
    )
    
    # ========================================================================
    # BUSINESS METHODS - Override Abstract Methods
    # ========================================================================
    
    @api.model
    def get_installment_options(self, amount, currency=None, bin_number=None):
        """Get installment options for this payment method.
        
        Integrates with Turkish POS to fetch installment options based on
        BIN number and amount.
        
        Args:
            amount (float): Payment amount
            currency (res.currency): Payment currency
            bin_number (str): Card BIN number (first 6 digits)
            
        Returns:
            list: List of installment options
        """
        self.ensure_one()
        
        if not self.supports_installments:
            return []
        
        if not self.turkish_pos_enabled:
            # Default installment calculation without Turkish POS
            return self._calculate_default_installments(amount, currency)
        
        # Use Turkish POS integration
        try:
            if bin_number:
                # Try to find bank by BIN
                Bin = self.env['turkish.pos.bin'].sudo()
                bin_record = Bin.search([
                    ('bin_number', '=', bin_number[:6])
                ], limit=1)
                
                if bin_record and bin_record.bank_id:
                    banks = bin_record.bank_id
                else:
                    banks = self.turkish_pos_bank_ids
            else:
                banks = self.turkish_pos_bank_ids
            
            installments = []
            for bank in banks:
                bank_options = bank.get_installment_options(amount, currency)
                if bank_options:
                    installments.append({
                        'bank': {
                            'id': bank.id,
                            'name': bank.name,
                            'code': bank.code,
                        },
                        'installments': bank_options,
                    })
            
            return installments
            
        except Exception as e:
            _logger.error("Error getting installment options: %s", str(e))
            return []
    
    def _calculate_default_installments(self, amount, currency=None):
        """Calculate default installment options without Turkish POS.
        
        Args:
            amount (float): Payment amount
            currency (res.currency): Payment currency
            
        Returns:
            list: Default installment options
        """
        self.ensure_one()
        
        if amount < self.min_installment_amount:
            return []
        
        installments = []
        for count in [1, 2, 3, 6, 9, 12]:
            if count > self.max_installments:
                break
            
            # Simple interest calculation (2% per installment beyond single payment)
            interest_rate = 0.0 if count == 1 else (count - 1) * 2.0
            total_amount = amount * (1 + interest_rate / 100)
            installment_amount = total_amount / count
            
            installments.append({
                'installment_count': count,
                'installment_amount': round(installment_amount, 2),
                'total_amount': round(total_amount, 2),
                'interest_rate': interest_rate,
                'is_campaign': False,
            })
        
        return installments
    
    def initiate_payment(self, amount, currency, reference, **kwargs):
        """Initiate payment transaction.
        
        Args:
            amount (float): Payment amount
            currency (res.currency): Payment currency  
            reference (str): Transaction reference
            **kwargs: Additional parameters (card_data, installments, etc.)
            
        Returns:
            dict: Payment initiation result
        """
        self.ensure_one()
        
        # Validate amount first
        validation = self.validate_payment_amount(amount, currency)
        if not validation['success']:
            return validation
        
        # Delegate to specific payment type handler
        if self.payment_type == 'cash':
            return self._initiate_cash_payment(amount, currency, reference, **kwargs)
        elif self.payment_type == 'card':
            return self._initiate_card_payment(amount, currency, reference, **kwargs)
        elif self.payment_type == 'bank_transfer':
            return self._initiate_bank_transfer(amount, currency, reference, **kwargs)
        else:
            return {
                'success': False,
                'message': _('Payment type %s not implemented') % self.payment_type
            }
    
    def _initiate_cash_payment(self, amount, currency, reference, **kwargs):
        """Handle cash payment initiation."""
        # Cash payments are typically handled offline
        return {
            'success': True,
            'message': _('Cash payment initiated. Please collect cash from customer.'),
            'payment_type': 'cash',
            'requires_action': False,
        }
    
    def _initiate_card_payment(self, amount, currency, reference, **kwargs):
        """Handle card payment initiation with optional 3D Secure."""
        card_data = kwargs.get('card_data', {})
        installments = kwargs.get('installments', 1)
        
        if not card_data:
            return {
                'success': False,
                'message': _('Card data is required for card payments.')
            }
        
        # If gateway exists and 3D Secure is required, redirect to 3D
        if self.gateway_id and self.requires_3d_secure:
            return {
                'success': True,
                'requires_3d': True,
                'redirect_url': '/payment/abstract/process',
                'message': _('Redirecting to 3D Secure authentication...'),
            }
        
        # Direct payment without 3D Secure
        return {
            'success': True,
            'message': _('Card payment processed successfully.'),
            'payment_type': 'card',
            'installments': installments,
        }
    
    def _initiate_bank_transfer(self, amount, currency, reference, **kwargs):
        """Handle bank transfer initiation."""
        return {
            'success': True,
            'message': _('Bank transfer initiated. Please transfer funds to the provided account.'),
            'payment_type': 'bank_transfer',
            'requires_confirmation': True,
        }
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    @api.model
    def get_payment_methods_for_checkout(self, currency=None, amount=None):
        """Get payment methods available for checkout.
        
        Args:
            currency (res.currency): Transaction currency
            amount (float): Transaction amount
            
        Returns:
            recordset: Available payment methods
        """
        domain = [
            ('active', '=', True),
            ('show_on_checkout', '=', True),
        ]
        
        methods = self.search(domain, order='sequence, name')
        
        # Apply currency and amount filters
        if currency:
            methods = methods.filtered(
                lambda m: not m.supported_currency_ids or currency in m.supported_currency_ids
            )
        
        if amount is not None:
            methods = methods.filtered(
                lambda m: (m.min_amount == 0 or amount >= m.min_amount) and
                         (m.max_amount == 0 or amount <= m.max_amount)
            )
        
        return methods
