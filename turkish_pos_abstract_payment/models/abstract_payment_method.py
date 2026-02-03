# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class AbstractPaymentMethod(models.AbstractModel):
    """Abstract base class for payment methods.
    
    This model provides a common interface for all payment method implementations.
    Each concrete payment method should inherit from this model and implement
    the required methods.
    
    Key features:
    - Multi-currency support (TRY, USD, EUR)
    - Payment validation
    - Transaction processing interface
    - Gateway integration hooks
    - 3D Secure support
    """
    
    _name = 'abstract.payment.method'
    _description = 'Abstract Payment Method'
    
    # ========================================================================
    # FIELDS
    # ========================================================================
    
    name = fields.Char(
        string='Method Name',
        required=True,
        translate=True,
        help='Display name of the payment method'
    )
    
    code = fields.Char(
        string='Method Code',
        required=True,
        help='Unique code identifier for this payment method (e.g., cash, credit_card)'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='If unchecked, this payment method will be hidden from users'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Display order in payment method selection'
    )
    
    description = fields.Text(
        string='Description',
        translate=True,
        help='Detailed description of this payment method'
    )
    
    # Currency Support
    supported_currency_ids = fields.Many2many(
        comodel_name='res.currency',
        string='Supported Currencies',
        help='Currencies supported by this payment method (TRY, USD, EUR, etc.)'
    )
    
    # Payment Type
    payment_type = fields.Selection(
        selection=[
            ('cash', 'Cash'),
            ('card', 'Credit/Debit Card'),
            ('bank_transfer', 'Bank Transfer'),
            ('digital_wallet', 'Digital Wallet'),
            ('other', 'Other'),
        ],
        string='Payment Type',
        required=True,
        default='other',
        help='Type of payment method'
    )
    
    # Card-specific fields
    supports_installments = fields.Boolean(
        string='Supports Installments',
        default=False,
        help='Whether this payment method supports installment payments'
    )
    
    requires_3d_secure = fields.Boolean(
        string='Requires 3D Secure',
        default=False,
        help='Whether this payment method requires 3D Secure authentication'
    )
    
    # Transaction limits
    min_amount = fields.Float(
        string='Minimum Amount',
        default=0.0,
        digits=(12, 2),
        help='Minimum transaction amount for this payment method'
    )
    
    max_amount = fields.Float(
        string='Maximum Amount',
        default=0.0,
        digits=(12, 2),
        help='Maximum transaction amount (0 = no limit)'
    )
    
    # Gateway Integration
    gateway_id = fields.Many2one(
        comodel_name='payment.gateway',
        string='Payment Gateway',
        help='Payment gateway/provider for this method'
    )
    
    # ========================================================================
    # COMPUTED FIELDS
    # ========================================================================
    
    @api.depends('supported_currency_ids')
    def _compute_currency_codes(self):
        """Compute comma-separated list of supported currency codes."""
        for record in self:
            if record.supported_currency_ids:
                record.currency_codes = ', '.join(
                    record.supported_currency_ids.mapped('name')
                )
            else:
                record.currency_codes = ''
    
    currency_codes = fields.Char(
        string='Currency Codes',
        compute='_compute_currency_codes',
        store=False,
        help='Comma-separated list of supported currency codes'
    )
    
    # ========================================================================
    # CONSTRAINTS
    # ========================================================================
    
    @api.constrains('min_amount', 'max_amount')
    def _check_amount_limits(self):
        """Validate that min_amount <= max_amount."""
        for record in self:
            if record.max_amount > 0 and record.min_amount > record.max_amount:
                raise ValidationError(_(
                    'Minimum amount (%.2f) cannot be greater than maximum amount (%.2f).'
                ) % (record.min_amount, record.max_amount))
    
    @api.constrains('code')
    def _check_code_format(self):
        """Validate that code contains only lowercase letters, numbers, and underscores."""
        for record in self:
            if record.code and not record.code.replace('_', '').isalnum():
                raise ValidationError(_(
                    'Payment method code must contain only lowercase letters, numbers, and underscores.'
                ))
            if record.code and record.code != record.code.lower():
                raise ValidationError(_(
                    'Payment method code must be in lowercase.'
                ))
    
    # ========================================================================
    # BUSINESS METHODS
    # ========================================================================
    
    def validate_payment_amount(self, amount, currency=None):
        """Validate if the payment amount is acceptable for this method.
        
        Args:
            amount (float): Payment amount to validate
            currency (res.currency): Currency of the payment
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        self.ensure_one()
        
        if amount <= 0:
            return {
                'success': False,
                'message': _('Payment amount must be greater than zero.')
            }
        
        if self.min_amount > 0 and amount < self.min_amount:
            return {
                'success': False,
                'message': _('Payment amount (%.2f) is below the minimum (%.2f).') % (
                    amount, self.min_amount
                )
            }
        
        if self.max_amount > 0 and amount > self.max_amount:
            return {
                'success': False,
                'message': _('Payment amount (%.2f) exceeds the maximum (%.2f).') % (
                    amount, self.max_amount
                )
            }
        
        # Check currency support
        if currency and self.supported_currency_ids:
            if currency not in self.supported_currency_ids:
                return {
                    'success': False,
                    'message': _('Currency %s is not supported by this payment method.') % currency.name
                }
        
        return {
            'success': True,
            'message': _('Payment amount is valid.')
        }
    
    def get_installment_options(self, amount, currency=None, bin_number=None):
        """Get available installment options for this payment method.
        
        This is a hook method that should be overridden by concrete implementations
        that support installments.
        
        Args:
            amount (float): Payment amount
            currency (res.currency): Payment currency
            bin_number (str): Card BIN number (first 6 digits)
            
        Returns:
            list: List of installment option dictionaries:
                [{
                    'installment_count': int,
                    'installment_amount': float,
                    'total_amount': float,
                    'interest_rate': float,
                    'is_campaign': bool,
                }]
        """
        self.ensure_one()
        
        if not self.supports_installments:
            return []
        
        # Default implementation - override in concrete classes
        _logger.info("get_installment_options called for %s - should be overridden", self.code)
        return []
    
    def initiate_payment(self, amount, currency, reference, **kwargs):
        """Initiate a payment transaction.
        
        This method should be overridden by concrete implementations to handle
        the actual payment initiation logic (e.g., creating gateway transaction,
        generating 3D Secure form, etc.).
        
        Args:
            amount (float): Payment amount
            currency (res.currency): Payment currency
            reference (str): Unique transaction reference
            **kwargs: Additional payment parameters
            
        Returns:
            dict: {
                'success': bool,
                'transaction_id': int (optional),
                'redirect_url': str (optional, for 3D Secure),
                'redirect_form_html': str (optional, for 3D Secure),
                'message': str,
            }
        """
        self.ensure_one()
        
        # Validate amount
        validation = self.validate_payment_amount(amount, currency)
        if not validation['success']:
            return validation
        
        # Default implementation - override in concrete classes
        _logger.warning(
            "initiate_payment called for %s but not implemented - should be overridden",
            self.code
        )
        
        return {
            'success': False,
            'message': _('Payment initiation not implemented for this method.')
        }
    
    def process_payment_return(self, transaction_data):
        """Process payment return callback (e.g., from 3D Secure).
        
        This method should be overridden by concrete implementations to handle
        the payment return logic after 3D Secure or other redirect flows.
        
        Args:
            transaction_data (dict): Transaction data from gateway callback
            
        Returns:
            dict: {
                'success': bool,
                'transaction_id': int,
                'status': str,
                'message': str,
            }
        """
        self.ensure_one()
        
        # Default implementation - override in concrete classes
        _logger.warning(
            "process_payment_return called for %s but not implemented - should be overridden",
            self.code
        )
        
        return {
            'success': False,
            'message': _('Payment return processing not implemented for this method.')
        }
    
    def complete_payment(self, transaction_id):
        """Complete a pending payment transaction.
        
        This method should be overridden by concrete implementations to finalize
        the payment after successful 3D Secure or other verification.
        
        Args:
            transaction_id (int): ID of the payment transaction
            
        Returns:
            dict: {
                'success': bool,
                'status': str,
                'message': str,
            }
        """
        self.ensure_one()
        
        # Default implementation - override in concrete classes
        _logger.warning(
            "complete_payment called for %s but not implemented - should be overridden",
            self.code
        )
        
        return {
            'success': False,
            'message': _('Payment completion not implemented for this method.')
        }
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _get_gateway_credentials(self):
        """Get gateway credentials for this payment method.
        
        Returns:
            dict: Gateway credentials
        """
        self.ensure_one()
        
        if not self.gateway_id:
            return {}
        
        # Gateway should have credentials field - will be implemented in gateway model
        return {}
    
    @api.model
    def get_available_methods(self, currency=None, amount=None):
        """Get all available payment methods for given criteria.
        
        Args:
            currency (res.currency): Filter by currency support
            amount (float): Filter by amount limits
            
        Returns:
            recordset: Available payment methods
        """
        domain = [('active', '=', True)]
        
        methods = self.search(domain, order='sequence, name')
        
        # Filter by currency if provided
        if currency and methods:
            methods = methods.filtered(
                lambda m: not m.supported_currency_ids or currency in m.supported_currency_ids
            )
        
        # Filter by amount if provided
        if amount is not None and methods:
            methods = methods.filtered(
                lambda m: (m.min_amount == 0 or amount >= m.min_amount) and
                         (m.max_amount == 0 or amount <= m.max_amount)
            )
        
        return methods
