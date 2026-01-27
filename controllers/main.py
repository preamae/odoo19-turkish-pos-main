# -*- coding: utf-8 -*-
import logging
import pprint
import json

from odoo import http, _, SUPERUSER_ID
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TurkishPosController(http.Controller):
    """Controller for Turkish Virtual POS payment operations.

    Provides endpoints for:
    - Fetching installment options based on card BIN number
    - Validating bank gateway configurations
    - Handling 3D Secure return callbacks from banks
    """

    # ------------------------------------------------------------------
    # JSON API: Installment Lookup
    # ------------------------------------------------------------------

    @http.route(
        '/turkish_pos/get_payment_installments',
        type='json',
        auth='public',
        methods=['POST'],
        csrf=False,
        website=True,
    )
    def get_payment_installments(self, amount=0, bank_id=None, bin_number=None, **kwargs):
        """Return available installment options for a given amount and card BIN.

        Workflow:
            1. BIN lookup -> detect issuing bank
            2. Fallback to bank_id parameter or default provider banks
            3. For each matched bank, load installment configs
            4. Respect product category restrictions
            5. Calculate monthly amounts and totals

        Args:
            amount (float): Payment amount in base currency.
            bank_id (int): Optional explicit bank ID override.
            bin_number (str): First 6 digits of card number for BIN lookup.

        Returns:
            dict: {
                'success': bool,
                'installments': [{
                    'bank': {'id': int, 'name': str, 'code': str},
                    'installments': [{
                        'installment_count': int,
                        'installment_amount': float,
                        'total_amount': float,
                        'interest_rate': float,
                        'is_campaign': bool,
                    }]
                }],
                'amount': float,
            }
        """
        try:
            amount = float(amount or 0)
        except (ValueError, TypeError):
            _logger.warning("Invalid amount value received: %r", amount)
            return {
                'success': False,
                'error': _('Gecersiz tutar.'),
            }

        if amount <= 0:
            return {
                'success': False,
                'error': _('Gecersiz tutar.'),
            }

        try:
            env = request.env
            banks = env['turkish.pos.bank'].sudo()
            detected_bank = None

            # Step 1: BIN lookup
            if bin_number:
                bin_number = str(bin_number).strip()[:6]
                if len(bin_number) == 6 and bin_number.isdigit():
                    bin_record = env['turkish.pos.bin'].sudo().search(
                        [('bin_number', '=', bin_number)], limit=1
                    )
                    if bin_record and bin_record.bank_id:
                        detected_bank = bin_record.bank_id

            # Step 2: Fallback to explicit bank_id
            if not detected_bank and bank_id:
                try:
                    detected_bank = banks.browse(int(bank_id)).exists()
                except (ValueError, TypeError):
                    pass

            # Step 3: Determine target banks
            if detected_bank:
                target_banks = detected_bank
            else:
                # Fallback: use all active banks from the turkish_pos provider
                provider = env['payment.provider'].sudo().search(
                    [('code', '=', 'turkish_pos'), ('state', '!=', 'disabled')],
                    limit=1,
                )
                if provider and provider.turkish_pos_bank_ids:
                    target_banks = provider.turkish_pos_bank_ids
                else:
                    target_banks = banks.search([('active', '=', True)])

            if not target_banks:
                return {
                    'success': True,
                    'installments': [],
                    'amount': amount,
                }

            # Step 4: Collect category restrictions from current order
            restricted_categories = self._get_order_category_ids()

            # Step 5: Build installment data per bank
            result_installments = []
            for bank in target_banks:
                try:
                    bank_installments = self._compute_bank_installments(
                        bank, amount, restricted_categories
                    )
                    if bank_installments:
                        result_installments.append({
                            'bank': {
                                'id': bank.id,
                                'name': bank.name,
                                'code': bank.code or '',
                            },
                            'installments': bank_installments,
                        })
                except Exception as be:
                    _logger.warning(
                        "Error computing installments for bank %s: %s",
                        bank.name, be
                    )
                    continue

            return {
                'success': True,
                'installments': result_installments,
                'amount': amount,
            }

        except Exception as e:
            _logger.exception("Error fetching installment options: %s", e)
            return {
                'success': False,
                'error': _('Taksit secenekleri yuklenirken hata olustu.'),
            }

    def _get_order_category_ids(self):
        """Extract product public category IDs from the current sale order.

        Returns:
            list[int]: List of product.public.category IDs in the order.
        """
        try:
            sale_order = request.website.sale_get_order()
            if not sale_order:
                return []

            category_ids = set()
            for line in sale_order.order_line:
                product = line.product_id
                if product and product.product_tmpl_id.public_categ_ids:
                    category_ids.update(product.product_tmpl_id.public_categ_ids.ids)
            return list(category_ids)
        except Exception as e:
            _logger.warning("Could not get order category IDs: %s", e)
            return []

    def _compute_bank_installments(self, bank, amount, restricted_category_ids):
        """Compute installment options for a single bank.

        Takes into account category restrictions that may limit
        the maximum installment count for certain product categories.

        Args:
            bank: turkish.pos.bank recordset (singleton).
            amount (float): The payment amount.
            restricted_category_ids (list[int]): Product category IDs in order.

        Returns:
            list[dict]: List of installment option dicts.
        """
        env = request.env
        installment_configs = env['turkish.pos.installment.config'].sudo().search(
            [
                ('bank_id', '=', bank.id),
                ('active', '=', True),
                ('min_amount', '<=', amount),
            ],
            order='installment_count asc',
        )

        if not installment_configs:
            return []

        # Determine max allowed installment count considering category restrictions
        max_allowed = 99
        blocked_installments = []
        if restricted_category_ids:
            restrictions = env['turkish.pos.category.restriction'].sudo().search([
                ('bank_id', '=', bank.id),
                ('category_id', 'in', restricted_category_ids),
            ])
            if restrictions:
                max_allowed = min(r.max_installment for r in restrictions)
                for r in restrictions:
                    blocked_installments.extend(r.get_blocked_installment_list())

        result = []
        for config in installment_configs:
            if config.installment_count > max_allowed:
                continue
            if config.installment_count in blocked_installments:
                continue

            inst_data = config.calculate_installment(amount)
            result.append({
                'installment_count': inst_data['installment_count'],
                'installment_amount': inst_data['installment_amount'],
                'total_amount': inst_data['total_amount'],
                'interest_rate': inst_data['interest_rate'],
                'is_campaign': inst_data.get('is_campaign', False),
            })

        # Always ensure single payment (pesin) option is present
        if not any(r['installment_count'] == 1 for r in result):
            result.insert(0, {
                'installment_count': 1,
                'installment_amount': round(amount, 2),
                'total_amount': round(amount, 2),
                'interest_rate': 0.0,
                'is_campaign': False,
            })

        return result

    # ------------------------------------------------------------------
    # JSON API: Bank Configuration Validation
    # ------------------------------------------------------------------

    @http.route(
        '/turkish_pos/validate_bank_config',
        type='json',
        auth='user',
        methods=['POST'],
        website=True,
    )
    def validate_bank_config(self, bank_id=None, gateway_id=None, **kwargs):
        """Validate that a bank has the required gateway credentials before payment.

        Checks that the bank's assigned gateway has all required credential
        fields filled in for the current provider state (test or production).

        Args:
            bank_id (int): The bank to validate.
            gateway_id (int): Optional specific gateway to validate.

        Returns:
            dict: {
                'success': bool,
                'valid': bool,
                'message': str,
                'missing_fields': list[str],
            }
        """
        try:
            if not bank_id:
                return {
                    'success': False,
                    'valid': False,
                    'message': _('Bank ID is required.'),
                }

            env = request.env
            bank = env['turkish.pos.bank'].sudo().browse(int(bank_id))
            if not bank.exists():
                return {
                    'success': False,
                    'valid': False,
                    'message': _('Bank not found.'),
                }

            provider = env['payment.provider'].sudo().search(
                [('code', '=', 'turkish_pos'), ('state', '!=', 'disabled')],
                limit=1,
            )
            if not provider:
                return {
                    'success': False,
                    'valid': False,
                    'message': _('Turkish POS provider is not configured.'),
                }

            # Determine which gateway to check
            gateway = None
            if gateway_id:
                gateway = env['turkish.pos.gateway'].sudo().browse(int(gateway_id))
                if not gateway.exists():
                    gateway = None

            if not gateway:
                # Pick the first gateway that supports this bank
                gateways = bank.gateway_ids.filtered(lambda g: g.active)
                if not gateways:
                    return {
                        'success': True,
                        'valid': False,
                        'message': _('No active gateway configured for this bank.'),
                        'missing_fields': [],
                    }
                gateway = gateways[0]

            # Check credentials
            missing_fields = []

            if not gateway.credentials:
                missing_fields.append(_('Kimlik Bilgileri (JSON)'))
            else:
                try:
                    cred_data = json.loads(gateway.credentials)
                    if not cred_data or not isinstance(cred_data, dict):
                        missing_fields.append(_('Credentials are empty or invalid.'))
                    else:
                        # Check for empty values in credentials
                        empty_keys = [k for k, v in cred_data.items() if not v]
                        if empty_keys:
                            missing_fields.extend(empty_keys)
                except (json.JSONDecodeError, TypeError):
                    missing_fields.append(_('Credentials JSON is malformed.'))

            is_valid = len(missing_fields) == 0
            if is_valid:
                message = _('Bank configuration is valid.')
            else:
                message = _(
                    'Bank configuration is incomplete. Missing: %s',
                    ', '.join(str(f) for f in missing_fields),
                )

            return {
                'success': True,
                'valid': is_valid,
                'message': message,
                'missing_fields': [str(f) for f in missing_fields],
            }

        except Exception as e:
            _logger.exception("Error validating bank config: %s", e)
            return {
                'success': False,
                'valid': False,
                'message': _('An error occurred during validation.'),
            }

    # ------------------------------------------------------------------
    # HTTP: 3D Secure Return Handler
    # ------------------------------------------------------------------

    @http.route(
        '/payment/turkish_pos/return',
        type='http',
        auth='public',
        methods=['GET', 'POST'],
        csrf=False,
        save_session=False,
        website=True,
    )
    def turkish_pos_return(self, **kwargs):
        """Handle the return callback from a bank's 3D Secure flow.

        This endpoint is called by the bank after the customer completes
        (or cancels) the 3D Secure verification step. It processes the
        bank's response data, updates the Odoo payment transaction, and
        redirects the customer to the standard payment status page.

        The bank may send data via GET query parameters or POST form data.

        Returns:
            werkzeug.wrappers.Response: Redirect to /payment/status.
        """
        _logger.info(
            "3D Secure return received with data:\n%s",
            pprint.pformat(kwargs),
        )

        try:
            # Merge GET and POST data
            notification_data = dict(request.httprequest.values)
            notification_data.update(kwargs)

            _logger.info(
                "Processing 3D Secure notification data:\n%s",
                pprint.pformat(notification_data),
            )

            # Find the corresponding transaction
            tx = self._find_transaction(notification_data)
            if not tx:
                _logger.error("No transaction found for 3D Secure return data.")
                return request.render(
                    'turkish_pos.payment_error',
                    {
                        'error_message': _('Odeme islemi bulunamadi. Lutfen destek ile iletisime gecin.'),
                        'error_code': 'TX_NOT_FOUND',
                    },
                )

            # Process the notification through the payment transaction model
            tx.sudo()._handle_notification_data('turkish_pos', notification_data)

        except ValidationError as e:
            _logger.exception("Validation error processing 3D Secure return: %s", e)
            return request.render(
                'turkish_pos.payment_error',
                {
                    'error_message': str(e),
                    'error_code': 'VALIDATION_ERROR',
                },
            )
        except Exception as e:
            _logger.exception("Unexpected error processing 3D Secure return: %s", e)
            return request.render(
                'turkish_pos.payment_error',
                {
                    'error_message': _('Beklenmeyen bir hata olustu. Lutfen tekrar deneyin.'),
                    'error_code': 'INTERNAL_ERROR',
                },
            )

        return request.redirect('/payment/status')

    def _find_transaction(self, notification_data):
        """Locate the payment.transaction record for the 3D Secure return.

        Searches by multiple possible reference fields that different
        Turkish payment gateways may use.

        Args:
            notification_data (dict): The raw data from the bank callback.

        Returns:
            payment.transaction recordset or None.
        """
        env = request.env
        tx = None

        # Common reference field names used by Turkish gateways
        reference_keys = [
            'merchant_order_id',
            'MerchantOrderId',
            'orderid',
            'OrderId',
            'order_id',
            'oid',
            'TransId',
            'trans_id',
            'reference',
            'ReturnOid',
            'TURKPOS_RETVAL_Siparis_ID',
            'conversationId',
            'ConversationId',
            'MerchantOrderNo',
        ]

        for key in reference_keys:
            ref_value = notification_data.get(key)
            if ref_value:
                tx = env['payment.transaction'].sudo().search(
                    [('reference', '=', str(ref_value))], limit=1
                )
                if tx:
                    _logger.info(
                        "Found transaction %s via key '%s' = '%s'",
                        tx.reference, key, ref_value,
                    )
                    return tx

        # Fallback: search by provider reference
        provider_ref_keys = [
            'AuthCode',
            'authcode',
            'auth_code',
            'ProvisionNumber',
            'provisionNumber',
            'hostlogkey',
            'HostLogKey',
        ]
        for key in provider_ref_keys:
            ref_value = notification_data.get(key)
            if ref_value:
                tx = env['payment.transaction'].sudo().search(
                    [('provider_reference', '=', str(ref_value))], limit=1
                )
                if tx:
                    _logger.info(
                        "Found transaction %s via provider reference key '%s' = '%s'",
                        tx.reference, key, ref_value,
                    )
                    return tx

        # Fallback: search by turkish_pos_transaction reference
        tp_tx_keys = ['TURKPOS_RETVAL_Islem_ID', 'tp_transaction_id']
        for key in tp_tx_keys:
            ref_value = notification_data.get(key)
            if ref_value:
                tp_tx = env['turkish.pos.transaction'].sudo().search(
                    [('transaction_id', '=', str(ref_value))], limit=1
                )
                if tp_tx and tp_tx.payment_transaction_id:
                    tx = tp_tx.payment_transaction_id
                    _logger.info(
                        "Found transaction %s via turkish.pos.transaction key '%s' = '%s'",
                        tx.reference, key, ref_value,
                    )
                    return tx

        return None
