# -*- coding: utf-8 -*-

import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class PaymentGateway(models.Model):
    """Payment Gateway Model.
    
    Represents a payment gateway/provider that can process payments.
    Stores gateway credentials and configuration.
    """
    
    _name = 'payment.gateway'
    _description = 'Payment Gateway'
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Gateway Name',
        required=True,
        translate=True,
        help='Display name of the payment gateway'
    )
    
    code = fields.Char(
        string='Gateway Code',
        required=True,
        help='Unique code identifier for this gateway (e.g., dummy_gateway, param, tosla)'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='If unchecked, this gateway will be disabled'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Display order'
    )
    
    # Credentials stored as JSON
    credentials = fields.Text(
        string='Credentials',
        help='Gateway credentials in JSON format (API keys, merchant ID, etc.)'
    )
    
    # Environment
    environment = fields.Selection(
        selection=[
            ('test', 'Test/Sandbox'),
            ('production', 'Production'),
        ],
        string='Environment',
        default='test',
        required=True,
        help='Gateway environment mode'
    )
    
    # Gateway URLs
    payment_url = fields.Char(
        string='Payment URL',
        help='URL for initiating payments'
    )
    
    callback_url = fields.Char(
        string='Callback URL',
        help='URL for receiving payment callbacks'
    )
    
    # Gateway Type
    gateway_type = fields.Selection(
        selection=[
            ('direct', 'Direct Payment'),
            ('redirect', 'Redirect (3D Secure)'),
            ('hosted', 'Hosted Payment Page'),
        ],
        string='Gateway Type',
        default='redirect',
        help='Type of payment flow'
    )
    
    # Supported Features
    supports_3d_secure = fields.Boolean(
        string='Supports 3D Secure',
        default=True,
        help='Gateway supports 3D Secure authentication'
    )
    
    supports_installments = fields.Boolean(
        string='Supports Installments',
        default=False,
        help='Gateway supports installment payments'
    )
    
    supports_refunds = fields.Boolean(
        string='Supports Refunds',
        default=True,
        help='Gateway supports payment refunds'
    )
    
    # Configuration
    timeout = fields.Integer(
        string='Timeout (seconds)',
        default=30,
        help='Request timeout in seconds'
    )
    
    retry_count = fields.Integer(
        string='Retry Count',
        default=3,
        help='Number of retry attempts for failed requests'
    )
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Gateway code must be unique!'),
    ]
    
    # ========================================================================
    # CREDENTIAL MANAGEMENT
    # ========================================================================
    
    def get_credentials(self):
        """Get gateway credentials as dictionary.
        
        Returns:
            dict: Gateway credentials
        """
        self.ensure_one()
        
        if not self.credentials:
            return {}
        
        try:
            return json.loads(self.credentials)
        except json.JSONDecodeError as e:
            _logger.error("Invalid JSON in gateway credentials for %s: %s", self.code, str(e))
            return {}
    
    def set_credentials(self, credentials_dict):
        """Set gateway credentials from dictionary.
        
        Args:
            credentials_dict (dict): Credentials to store
        """
        self.ensure_one()
        
        if not isinstance(credentials_dict, dict):
            raise ValidationError(_('Credentials must be a dictionary'))
        
        self.credentials = json.dumps(credentials_dict, indent=2)
    
    @api.constrains('credentials')
    def _check_credentials_json(self):
        """Validate that credentials field contains valid JSON."""
        for record in self:
            if record.credentials:
                try:
                    json.loads(record.credentials)
                except json.JSONDecodeError:
                    raise ValidationError(_(
                        'Credentials must be valid JSON format'
                    ))
    
    # ========================================================================
    # PAYMENT OPERATIONS
    # ========================================================================
    
    def initiate_payment(self, amount, currency, card_data, reference, **kwargs):
        """Initiate a payment through this gateway.
        
        Args:
            amount (float): Payment amount
            currency (res.currency): Payment currency
            card_data (dict): Card information
            reference (str): Transaction reference
            **kwargs: Additional parameters
            
        Returns:
            dict: Payment response
        """
        self.ensure_one()
        
        if not self.active:
            return {
                'success': False,
                'message': _('Gateway %s is not active') % self.name
            }
        
        # Delegate to specific gateway implementation
        if self.code == 'dummy_gateway':
            return self._initiate_dummy_payment(amount, currency, card_data, reference, **kwargs)
        else:
            raise NotImplementedError(_(
                'Payment initiation not implemented for gateway %s'
            ) % self.code)
    
    def _initiate_dummy_payment(self, amount, currency, card_data, reference, **kwargs):
        """Dummy gateway payment initiation for testing.
        
        This is a test implementation that simulates a payment gateway
        response without actually processing any real payment.
        
        Args:
            amount (float): Payment amount
            currency (res.currency): Payment currency
            card_data (dict): Card information
            reference (str): Transaction reference
            **kwargs: Additional parameters
            
        Returns:
            dict: Simulated payment response
        """
        self.ensure_one()
        
        _logger.info("Dummy gateway: Initiating payment for %.2f %s (ref: %s)",
                    amount, currency.name if currency else 'N/A', reference)
        
        # Simulate 3D Secure redirect
        if self.supports_3d_secure and kwargs.get('require_3d', True):
            return {
                'success': True,
                'requires_3d': True,
                'transaction_id': f'DUMMY-{reference}',
                'redirect_url': f'/payment/abstract/3d_secure?ref={reference}',
                'redirect_form_html': self._generate_dummy_3d_form(reference, amount, currency),
                'message': _('Redirecting to 3D Secure authentication...'),
            }
        
        # Direct payment (no 3D Secure)
        return {
            'success': True,
            'requires_3d': False,
            'transaction_id': f'DUMMY-{reference}',
            'status': 'success',
            'message': _('Payment processed successfully (dummy mode)'),
        }
    
    def _generate_dummy_3d_form(self, reference, amount, currency):
        """Generate dummy 3D Secure redirect form HTML.
        
        Args:
            reference (str): Transaction reference
            amount (float): Payment amount
            currency (res.currency): Payment currency
            
        Returns:
            str: HTML form for 3D Secure redirect
        """
        currency_name = currency.name if currency else 'TRY'
        
        return f'''
        <html>
        <head><title>3D Secure - Dummy Gateway</title></head>
        <body>
            <h2>3D Secure Kimlik Doğrulama (Test)</h2>
            <p>Bu bir test 3D Secure sayfasıdır.</p>
            <form id="secure3dForm" method="POST" action="/payment/abstract/3d_return">
                <input type="hidden" name="transaction_ref" value="{reference}" />
                <input type="hidden" name="amount" value="{amount}" />
                <input type="hidden" name="currency" value="{currency_name}" />
                <input type="hidden" name="status" value="success" />
                <input type="hidden" name="gateway_response" value="APPROVED" />
                
                <p>Referans: {reference}</p>
                <p>Tutar: {amount:.2f} {currency_name}</p>
                
                <button type="submit" style="margin: 10px; padding: 10px 20px; background: green; color: white; border: none; cursor: pointer;">
                    ✓ Ödemeyi Onayla (Test)
                </button>
                <button type="button" onclick="cancelPayment()" style="margin: 10px; padding: 10px 20px; background: red; color: white; border: none; cursor: pointer;">
                    ✗ Ödemeyi İptal Et (Test)
                </button>
            </form>
            
            <script>
                function cancelPayment() {{
                    document.getElementById('secure3dForm').status.value = 'cancelled';
                    document.getElementById('secure3dForm').gateway_response.value = 'CANCELLED';
                    document.getElementById('secure3dForm').submit();
                }}
            </script>
        </body>
        </html>
        '''
    
    def process_3d_return(self, transaction_data):
        """Process 3D Secure return callback.
        
        Args:
            transaction_data (dict): Data from 3D Secure callback
            
        Returns:
            dict: Processing result
        """
        self.ensure_one()
        
        if self.code == 'dummy_gateway':
            return self._process_dummy_3d_return(transaction_data)
        else:
            raise NotImplementedError(_(
                '3D Secure return processing not implemented for gateway %s'
            ) % self.code)
    
    def _process_dummy_3d_return(self, transaction_data):
        """Process dummy gateway 3D Secure return.
        
        Args:
            transaction_data (dict): Callback data
            
        Returns:
            dict: Processing result
        """
        self.ensure_one()
        
        status = transaction_data.get('status', 'failed')
        gateway_response = transaction_data.get('gateway_response', 'UNKNOWN')
        
        _logger.info("Dummy gateway: Processing 3D return - status: %s, response: %s",
                    status, gateway_response)
        
        if status == 'success' and gateway_response == 'APPROVED':
            return {
                'success': True,
                'status': 'success',
                'transaction_id': transaction_data.get('transaction_ref'),
                'message': _('Payment completed successfully (dummy mode)'),
            }
        else:
            return {
                'success': False,
                'status': 'failed',
                'transaction_id': transaction_data.get('transaction_ref'),
                'message': _('Payment failed or cancelled (dummy mode)'),
            }
    
    def process_refund(self, transaction_id, amount, currency):
        """Process a refund for a completed payment.
        
        Args:
            transaction_id (str): Original transaction ID
            amount (float): Refund amount
            currency (res.currency): Refund currency
            
        Returns:
            dict: Refund result
        """
        self.ensure_one()
        
        if not self.supports_refunds:
            return {
                'success': False,
                'message': _('Gateway %s does not support refunds') % self.name
            }
        
        if self.code == 'dummy_gateway':
            return self._process_dummy_refund(transaction_id, amount, currency)
        else:
            raise NotImplementedError(_(
                'Refund processing not implemented for gateway %s'
            ) % self.code)
    
    def _process_dummy_refund(self, transaction_id, amount, currency):
        """Process dummy refund for testing.
        
        Args:
            transaction_id (str): Original transaction ID
            amount (float): Refund amount
            currency (res.currency): Refund currency
            
        Returns:
            dict: Refund result
        """
        self.ensure_one()
        
        _logger.info("Dummy gateway: Processing refund for %s - amount: %.2f %s",
                    transaction_id, amount, currency.name if currency else 'N/A')
        
        return {
            'success': True,
            'refund_id': f'REFUND-{transaction_id}',
            'status': 'refunded',
            'message': _('Refund processed successfully (dummy mode)'),
        }
    
    # ========================================================================
    # VALIDATION
    # ========================================================================
    
    def validate_configuration(self):
        """Validate gateway configuration and credentials.
        
        Returns:
            dict: Validation result
        """
        self.ensure_one()
        
        errors = []
        
        if not self.code:
            errors.append(_('Gateway code is required'))
        
        if not self.credentials:
            errors.append(_('Gateway credentials are required'))
        else:
            try:
                creds = json.loads(self.credentials)
                if not isinstance(creds, dict):
                    errors.append(_('Credentials must be a JSON object'))
            except json.JSONDecodeError:
                errors.append(_('Credentials must be valid JSON'))
        
        if self.gateway_type == 'redirect' and not self.payment_url:
            errors.append(_('Payment URL is required for redirect gateways'))
        
        if errors:
            return {
                'success': False,
                'errors': errors,
                'message': _('Gateway configuration is invalid'),
            }
        
        return {
            'success': True,
            'message': _('Gateway configuration is valid'),
        }
