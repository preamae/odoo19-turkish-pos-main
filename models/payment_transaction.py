# -*- coding: utf-8 -*-

import json
import logging
import uuid

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    # ── Turkish POS specific fields ────────────────────────────────────
    turkish_pos_bank_id = fields.Many2one(
        comodel_name='turkish.pos.bank',
        string='Banka',
        help='Bu islem icin secilen banka.',
    )
    turkish_pos_installment_count = fields.Integer(
        string='Taksit Sayisi',
        default=1,
        help='Secilen taksit sayisi (1 = pesin).',
    )
    turkish_pos_transaction_id = fields.Many2one(
        comodel_name='turkish.pos.transaction',
        string='POS Islemi',
        ondelete='set null',
    )
    turkish_pos_card_number_masked = fields.Char(
        string='Maskeli Kart No',
    )
    turkish_pos_bin_number = fields.Char(
        string='BIN Numarasi',
        size=6,
    )
    turkish_pos_3d_html = fields.Text(
        string='3D Secure HTML',
        help='3D Secure yonlendirme HTML formu.',
    )

    def _get_specific_rendering_values(self, processing_values):
        """Override to add Turkish POS specific rendering values.

        Returns the 3D Secure HTML form that will be rendered on the payment page
        to redirect the customer to their bank for 3D authentication.
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'turkish_pos':
            return res

        _logger.info(
            "Turkish POS rendering values hazirlaniyor: tx=%s, tutar=%.2f",
            self.reference, self.amount,
        )

        # Build rendering values for 3D Secure form
        res.update({
            'turkish_pos_3d_html': self.turkish_pos_3d_html or '',
            'turkish_pos_bank_id': self.turkish_pos_bank_id.id if self.turkish_pos_bank_id else False,
            'turkish_pos_bank_name': self.turkish_pos_bank_id.name if self.turkish_pos_bank_id else '',
            'turkish_pos_installment_count': self.turkish_pos_installment_count,
            'api_url': self._get_turkish_pos_api_url(),
        })

        return res

    def _get_turkish_pos_api_url(self):
        """Return the appropriate API URL based on provider state."""
        self.ensure_one()
        base_url = self.provider_id.get_base_url()
        return '%s/turkish_pos/payment' % base_url

    def _send_payment_request(self):
        """Override to send payment request via Turkish POS gateway.

        Creates the turkish.pos.transaction record and initiates the payment
        flow through the appropriate bank integration.
        """
        super()._send_payment_request()
        if self.provider_code != 'turkish_pos':
            return

        _logger.info(
            "Turkish POS odeme istegi gonderiliyor: tx=%s, tutar=%.2f, taksit=%d",
            self.reference, self.amount, self.turkish_pos_installment_count,
        )

        bank = self.turkish_pos_bank_id
        if not bank:
            bank = self.provider_id.turkish_pos_default_bank_id
        if not bank:
            raise ValidationError(
                _('Odeme icin bir banka secilmedi ve varsayilan banka tanimli degil.')
            )

        # Find the gateway for this bank
        gateway = bank.gateway_ids[:1]
        if not gateway:
            raise ValidationError(
                _('Secilen banka (%s) icin tanimli bir gateway bulunamadi.') % bank.name
            )

        # Create turkish.pos.transaction record
        pos_tx = self.env['turkish.pos.transaction'].create({
            'transaction_id': str(uuid.uuid4()),
            'order_id': self.sale_order_ids[:1].id if self.sale_order_ids else False,
            'payment_transaction_id': self.id,
            'bank_id': bank.id,
            'gateway_id': gateway.id,
            'amount': self.amount,
            'currency': self.currency_id.name if self.currency_id.name in ('TRY', 'USD', 'EUR') else 'TRY',
            'installment_count': self.turkish_pos_installment_count,
            'state': 'pending',
            'is_3d_secure': gateway.payment_model in ('3d_secure', '3d_pay', '3d_host'),
        })
        self.turkish_pos_transaction_id = pos_tx.id

        # Initiate payment via bank integration
        try:
            from . import bank_integration
            integration = bank_integration.get_bank_integration(gateway, bank)
            if not integration:
                pos_tx.write({
                    'state': 'failed',
                    'error_message': _('Gateway entegrasyonu bulunamadi.'),
                })
                raise ValidationError(
                    _('Gateway entegrasyonu bulunamadi: %s') % gateway.code
                )

            pos_tx.write({'state': 'processing'})

            # Build payment parameters
            payment_params = {
                'amount': self.amount,
                'currency': pos_tx.currency,
                'installment_count': self.turkish_pos_installment_count,
                'order_id': self.reference,
                'transaction_id': pos_tx.transaction_id,
                'success_url': '%s/turkish_pos/callback/success' % self.provider_id.get_base_url(),
                'fail_url': '%s/turkish_pos/callback/fail' % self.provider_id.get_base_url(),
                'callback_url': '%s/turkish_pos/callback/notify' % self.provider_id.get_base_url(),
            }

            result = integration.create_payment_form(**payment_params)

            if result.get('success'):
                html_form = result.get('html_form', '')
                self.turkish_pos_3d_html = html_form
                pos_tx.write({
                    'state': 'waiting_3d',
                    'request_data': json.dumps(payment_params, default=str),
                })
                _logger.info("3D Secure formu olusturuldu: tx=%s", self.reference)
            else:
                error_msg = result.get('error_message', _('Bilinmeyen hata'))
                pos_tx.write({
                    'state': 'failed',
                    'error_message': error_msg,
                    'error_code': result.get('error_code', ''),
                    'request_data': json.dumps(payment_params, default=str),
                    'response_data': json.dumps(result, default=str),
                })
                raise ValidationError(
                    _('Odeme istegi basarisiz: %s') % error_msg
                )

        except ValidationError:
            raise
        except Exception as e:
            _logger.exception("Turkish POS odeme istegi hatasi: %s", str(e))
            pos_tx.write({
                'state': 'failed',
                'error_message': str(e),
            })
            raise ValidationError(
                _('Odeme islemi sirasinda hata olustu: %s') % str(e)
            )

    def _get_processing_values(self):
        """Override to add Turkish POS specific processing values."""
        res = super()._get_processing_values()
        if self.provider_code != 'turkish_pos':
            return res

        res.update({
            'turkish_pos_bank_id': self.turkish_pos_bank_id.id,
            'turkish_pos_installment_count': self.turkish_pos_installment_count,
            'turkish_pos_transaction_id': self.turkish_pos_transaction_id.transaction_id if self.turkish_pos_transaction_id else '',
        })
        return res

    def _process_notification_data(self, notification_data):
        """Override to process Turkish POS callback notification data.

        Called when the bank sends back the 3D Secure callback.
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'turkish_pos':
            return

        _logger.info(
            "Turkish POS bildirim verisi isleniyor: tx=%s",
            self.reference,
        )

        pos_tx = self.turkish_pos_transaction_id
        if not pos_tx:
            raise ValidationError(
                _('Bu islem icin POS kaydi bulunamadi: %s') % self.reference
            )

        # Process 3D response via bank integration
        try:
            from . import bank_integration
            integration = bank_integration.get_bank_integration(
                pos_tx.gateway_id, pos_tx.bank_id,
            )
            if not integration:
                raise ValidationError(
                    _('Gateway entegrasyonu bulunamadi.')
                )

            result = integration.process_3d_response(notification_data)

            # Update POS transaction
            pos_tx.write({
                'response_data': json.dumps(notification_data, default=str),
                'bank_response_code': result.get('response_code', ''),
                'bank_response_message': result.get('response_message', ''),
                'bank_order_id': result.get('bank_order_id', ''),
                'auth_code': result.get('auth_code', ''),
                'rrn': result.get('rrn', ''),
                'host_ref_num': result.get('host_ref_num', ''),
                'md_status': result.get('md_status', ''),
                'eci': result.get('eci', ''),
                'cavv': result.get('cavv', ''),
                'xid': result.get('xid', ''),
                'threed_status': result.get('threed_status', ''),
            })

            if result.get('success'):
                # Calculate final amounts
                installment_data = {}
                if pos_tx.installment_count > 1 and pos_tx.bank_id:
                    configs = pos_tx.bank_id.installment_config_ids.filtered(
                        lambda c: c.installment_count == pos_tx.installment_count and c.active
                    )
                    if configs:
                        installment_data = configs[0].calculate_installment(pos_tx.amount)

                total_amount = installment_data.get('total_amount', pos_tx.amount)
                installment_amount = installment_data.get(
                    'installment_amount', pos_tx.amount
                )

                pos_tx.write({
                    'state': 'success',
                    'total_amount': total_amount,
                    'installment_amount': installment_amount,
                    'card_number_masked': result.get('masked_card_number', ''),
                })

                # Update Odoo payment transaction state
                self._set_done()
                _logger.info(
                    "Turkish POS odeme basarili: tx=%s, tutar=%.2f",
                    self.reference, total_amount,
                )
            else:
                error_msg = result.get('error_message', _('Odeme basarisiz'))
                pos_tx.write({
                    'state': 'failed',
                    'error_message': error_msg,
                    'error_code': result.get('error_code', ''),
                })
                self._set_canceled(
                    state_message=_('Turkish POS odeme basarisiz: %s') % error_msg,
                )
                _logger.warning(
                    "Turkish POS odeme basarisiz: tx=%s, hata=%s",
                    self.reference, error_msg,
                )

        except ValidationError:
            raise
        except Exception as e:
            _logger.exception("Turkish POS bildirim isleme hatasi: %s", str(e))
            if pos_tx:
                pos_tx.write({
                    'state': 'failed',
                    'error_message': str(e),
                })
            self._set_error(
                state_message=_('Turkish POS bildirim isleme hatasi: %s') % str(e),
            )

    @api.model
    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Override to find the transaction from Turkish POS notification data."""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'turkish_pos':
            return tx

        reference = notification_data.get('merchant_order_id') or \
                    notification_data.get('orderid') or \
                    notification_data.get('OrderId') or \
                    notification_data.get('TURKPOS_RETVAL_Siparis_ID') or \
                    notification_data.get('conversationId')

        if not reference:
            raise ValidationError(
                _('Turkish POS bildirim verisinde siparis referansi bulunamadi.')
            )

        tx = self.search([
            ('reference', '=', reference),
            ('provider_code', '=', 'turkish_pos'),
        ], limit=1)

        if not tx:
            raise ValidationError(
                _('Turkish POS islemi bulunamadi: %s') % reference
            )

        return tx
