# -*- coding: utf-8 -*-

import json
import logging
import pprint
from werkzeug.exceptions import Forbidden

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AbstractPaymentController(http.Controller):
    """Controller for Abstract Payment operations.
    
    Provides endpoints for:
    - Payment method listing
    - Payment initiation
    - 3D Secure flow (redirect, callback, return)
    - Payment validation and completion
    """
    
    # ========================================================================
    # JSON API ENDPOINTS
    # ========================================================================
    
    @http.route(
        '/payment/abstract/methods',
        type='json',
        auth='public',
        methods=['POST'],
        csrf=False,
        website=True,
    )
    def get_payment_methods(self, amount=None, currency_id=None, **kwargs):
        """Get available payment methods for checkout.
        
        Args:
            amount (float): Transaction amount for filtering methods
            currency_id (int): Currency ID for filtering methods
            
        Returns:
            dict: {
                'success': bool,
                'methods': [list of payment method data],
                'error': str (if failed),
            }
        """
        try:
            PaymentMethod = request.env['payment.method'].sudo()
            
            # Get currency
            currency = None
            if currency_id:
                Currency = request.env['res.currency'].sudo()
                currency = Currency.browse(currency_id)
            
            # Get available methods
            methods = PaymentMethod.get_payment_methods_for_checkout(
                currency=currency,
                amount=amount
            )
            
            # Format response
            method_data = []
            for method in methods:
                method_data.append({
                    'id': method.id,
                    'name': method.name,
                    'code': method.code,
                    'payment_type': method.payment_type,
                    'description': method.description or '',
                    'supports_installments': method.supports_installments,
                    'requires_3d_secure': method.requires_3d_secure,
                    'min_amount': method.min_amount,
                    'max_amount': method.max_amount,
                    'sequence': method.sequence,
                })
            
            return {
                'success': True,
                'methods': method_data,
            }
            
        except Exception as e:
            _logger.exception("Error getting payment methods")
            return {
                'success': False,
                'error': str(e),
            }
    
    @http.route(
        '/payment/abstract/installments',
        type='json',
        auth='public',
        methods=['POST'],
        csrf=False,
        website=True,
    )
    def get_installment_options(self, method_id, amount, currency_id=None, bin_number=None, **kwargs):
        """Get installment options for a payment method.
        
        Args:
            method_id (int): Payment method ID
            amount (float): Payment amount
            currency_id (int): Currency ID
            bin_number (str): Card BIN number (first 6 digits)
            
        Returns:
            dict: {
                'success': bool,
                'installments': list of installment options,
                'error': str (if failed),
            }
        """
        try:
            PaymentMethod = request.env['payment.method'].sudo()
            method = PaymentMethod.browse(method_id)
            
            if not method.exists():
                return {
                    'success': False,
                    'error': _('Payment method not found'),
                }
            
            # Get currency
            currency = None
            if currency_id:
                Currency = request.env['res.currency'].sudo()
                currency = Currency.browse(currency_id)
            
            # Get installment options
            installments = method.get_installment_options(
                amount=amount,
                currency=currency,
                bin_number=bin_number
            )
            
            return {
                'success': True,
                'installments': installments,
                'amount': amount,
            }
            
        except Exception as e:
            _logger.exception("Error getting installment options")
            return {
                'success': False,
                'error': str(e),
            }
    
    @http.route(
        '/payment/abstract/initiate',
        type='json',
        auth='public',
        methods=['POST'],
        csrf=False,
        website=True,
    )
    def initiate_payment(self, method_id, amount, currency_id, reference, **kwargs):
        """Initiate a payment transaction.
        
        This endpoint starts the payment process. For card payments with 3D Secure,
        it returns redirect information. For direct payments, it processes immediately.
        
        Args:
            method_id (int): Payment method ID
            amount (float): Payment amount
            currency_id (int): Currency ID
            reference (str): Transaction reference
            **kwargs: Additional payment data (card_data, installments, etc.)
            
        Returns:
            dict: {
                'success': bool,
                'requires_3d': bool,
                'redirect_url': str (if 3D Secure required),
                'redirect_form_html': str (if 3D Secure required),
                'transaction_id': str,
                'message': str,
                'error': str (if failed),
            }
        """
        try:
            PaymentMethod = request.env['payment.method'].sudo()
            Currency = request.env['res.currency'].sudo()
            
            method = PaymentMethod.browse(method_id)
            currency = Currency.browse(currency_id)
            
            if not method.exists():
                return {
                    'success': False,
                    'error': _('Payment method not found'),
                }
            
            if not currency.exists():
                return {
                    'success': False,
                    'error': _('Currency not found'),
                }
            
            # Initiate payment
            result = method.initiate_payment(
                amount=amount,
                currency=currency,
                reference=reference,
                **kwargs
            )
            
            _logger.info("Payment initiated - method: %s, amount: %.2f %s, result: %s",
                        method.code, amount, currency.name, result.get('success'))
            
            return result
            
        except Exception as e:
            _logger.exception("Error initiating payment")
            return {
                'success': False,
                'error': str(e),
            }
    
    @http.route(
        '/payment/abstract/validate',
        type='json',
        auth='public',
        methods=['POST'],
        csrf=False,
        website=True,
    )
    def validate_payment_data(self, method_id, amount, currency_id, **kwargs):
        """Validate payment data before submission.
        
        Args:
            method_id (int): Payment method ID
            amount (float): Payment amount
            currency_id (int): Currency ID
            **kwargs: Additional data to validate (card_data, etc.)
            
        Returns:
            dict: {
                'success': bool,
                'valid': bool,
                'errors': list of error messages,
            }
        """
        try:
            PaymentMethod = request.env['payment.method'].sudo()
            Currency = request.env['res.currency'].sudo()
            
            method = PaymentMethod.browse(method_id)
            currency = Currency.browse(currency_id)
            
            if not method.exists():
                return {
                    'success': False,
                    'valid': False,
                    'errors': [_('Payment method not found')],
                }
            
            if not currency.exists():
                return {
                    'success': False,
                    'valid': False,
                    'errors': [_('Currency not found')],
                }
            
            # Validate amount
            validation = method.validate_payment_amount(amount, currency)
            
            if not validation['success']:
                return {
                    'success': True,
                    'valid': False,
                    'errors': [validation['message']],
                }
            
            # Additional validation for card data
            errors = []
            if method.payment_type == 'card' and 'card_data' in kwargs:
                card_errors = self._validate_card_data(kwargs['card_data'])
                errors.extend(card_errors)
            
            return {
                'success': True,
                'valid': len(errors) == 0,
                'errors': errors,
            }
            
        except Exception as e:
            _logger.exception("Error validating payment data")
            return {
                'success': False,
                'valid': False,
                'errors': [str(e)],
            }
    
    # ========================================================================
    # 3D SECURE FLOW ENDPOINTS
    # ========================================================================
    
    @http.route(
        '/payment/abstract/3d_secure',
        type='http',
        auth='public',
        methods=['GET', 'POST'],
        csrf=False,
        website=True,
    )
    def process_3d_secure(self, ref=None, **kwargs):
        """Display 3D Secure authentication page.
        
        This endpoint is called after payment initiation to show the 3D Secure
        authentication form (either from gateway or dummy).
        
        Args:
            ref (str): Transaction reference
            **kwargs: Additional parameters
            
        Returns:
            Response: 3D Secure page or redirect
        """
        if not ref:
            return request.render('turkish_pos_abstract_payment.payment_error', {
                'error_message': _('Transaction reference is required'),
            })
        
        try:
            # In a real implementation, you would fetch the transaction
            # and display the actual 3D Secure form from the gateway
            
            # For now, use dummy gateway 3D form
            Gateway = request.env['payment.gateway'].sudo()
            dummy_gateway = Gateway.search([('code', '=', 'dummy_gateway')], limit=1)
            
            if dummy_gateway:
                form_html = dummy_gateway._generate_dummy_3d_form(
                    ref,
                    kwargs.get('amount', 0),
                    None
                )
                return request.make_response(
                    form_html,
                    headers=[('Content-Type', 'text/html; charset=utf-8')]
                )
            else:
                return request.render('turkish_pos_abstract_payment.payment_3d_secure', {
                    'transaction_ref': ref,
                    'amount': kwargs.get('amount', 0),
                })
            
        except Exception as e:
            _logger.exception("Error processing 3D Secure")
            return request.render('turkish_pos_abstract_payment.payment_error', {
                'error_message': str(e),
            })
    
    @http.route(
        '/payment/abstract/3d_return',
        type='http',
        auth='public',
        methods=['GET', 'POST'],
        csrf=False,
        website=True,
    )
    def handle_3d_return(self, **kwargs):
        """Handle 3D Secure return callback from bank.
        
        This endpoint receives the callback from the bank after 3D Secure
        authentication and processes the payment completion.
        
        Args:
            **kwargs: Callback data from bank
            
        Returns:
            Response: Success or error page
        """
        _logger.info("3D Secure return callback received with data: %s",
                    pprint.pformat(kwargs))
        
        try:
            transaction_ref = kwargs.get('transaction_ref')
            if not transaction_ref:
                raise ValidationError(_('Transaction reference not found in callback'))
            
            status = kwargs.get('status', 'failed')
            gateway_response = kwargs.get('gateway_response', 'UNKNOWN')
            
            # Process the return through gateway
            Gateway = request.env['payment.gateway'].sudo()
            dummy_gateway = Gateway.search([('code', '=', 'dummy_gateway')], limit=1)
            
            if dummy_gateway:
                result = dummy_gateway.process_3d_return(kwargs)
                
                if result['success']:
                    return request.render('turkish_pos_abstract_payment.payment_success', {
                        'transaction_ref': transaction_ref,
                        'message': result.get('message', _('Payment completed successfully')),
                    })
                else:
                    return request.render('turkish_pos_abstract_payment.payment_error', {
                        'transaction_ref': transaction_ref,
                        'error_message': result.get('message', _('Payment failed')),
                    })
            else:
                raise ValidationError(_('Payment gateway not found'))
            
        except Exception as e:
            _logger.exception("Error handling 3D Secure return")
            return request.render('turkish_pos_abstract_payment.payment_error', {
                'error_message': str(e),
            })
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _validate_card_data(self, card_data):
        """Validate card data fields.
        
        Args:
            card_data (dict): Card data to validate
            
        Returns:
            list: List of error messages (empty if valid)
        """
        errors = []
        
        # Card number
        card_number = card_data.get('card_number', '').replace(' ', '')
        if not card_number or not card_number.isdigit():
            errors.append(_('Invalid card number'))
        elif len(card_number) < 13 or len(card_number) > 19:
            errors.append(_('Card number must be 13-19 digits'))
        
        # Cardholder name
        if not card_data.get('card_holder_name'):
            errors.append(_('Cardholder name is required'))
        
        # Expiry date
        expiry_month = card_data.get('expiry_month')
        expiry_year = card_data.get('expiry_year')
        
        if not expiry_month or not str(expiry_month).isdigit():
            errors.append(_('Invalid expiry month'))
        elif int(expiry_month) < 1 or int(expiry_month) > 12:
            errors.append(_('Expiry month must be 1-12'))
        
        if not expiry_year or not str(expiry_year).isdigit():
            errors.append(_('Invalid expiry year'))
        elif len(str(expiry_year)) != 4:
            errors.append(_('Expiry year must be 4 digits'))
        
        # CVV
        cvv = card_data.get('cvv', '')
        if not cvv or not cvv.isdigit():
            errors.append(_('Invalid CVV'))
        elif len(cvv) not in [3, 4]:
            errors.append(_('CVV must be 3 or 4 digits'))
        
        return errors
    
    @http.route(
        '/payment/abstract/test',
        type='http',
        auth='public',
        methods=['GET'],
        website=True,
    )
    def test_payment_page(self, **kwargs):
        """Test payment form page for development/testing.
        
        Returns:
            Response: Test payment form page
        """
        PaymentMethod = request.env['payment.method'].sudo()
        Currency = request.env['res.currency'].sudo()
        
        methods = PaymentMethod.search([('active', '=', True)], order='sequence')
        currencies = Currency.search([('name', 'in', ['TRY', 'USD', 'EUR'])])
        
        return request.render('turkish_pos_abstract_payment.test_payment_form', {
            'payment_methods': methods,
            'currencies': currencies,
        })
