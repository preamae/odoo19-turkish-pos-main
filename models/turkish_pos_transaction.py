# -*- coding: utf-8 -*-

import logging
import uuid
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class TurkishPosTransaction(models.Model):
    _name = 'turkish.pos.transaction'
    _description = 'Sanal POS Islem Kayitlari'
    _order = 'create_date desc'
    _rec_name = 'transaction_id'

    # ── Core identification ────────────────────────────────────────────
    transaction_id = fields.Char(
        string='Islem ID',
        required=True,
        readonly=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False,
        index=True,
    )
    order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Siparis',
        ondelete='set null',
        index=True,
    )
    payment_transaction_id = fields.Many2one(
        comodel_name='payment.transaction',
        string='Odeme Islemi',
        ondelete='set null',
        index=True,
    )
    bank_id = fields.Many2one(
        comodel_name='turkish.pos.bank',
        string='Banka',
        ondelete='restrict',
    )
    gateway_id = fields.Many2one(
        comodel_name='turkish.pos.gateway',
        string='Gateway',
        ondelete='restrict',
    )

    # ── Amount fields ──────────────────────────────────────────────────
    amount = fields.Float(
        string='Tutar',
        digits=(12, 2),
        required=True,
    )
    currency = fields.Selection(
        selection=[
            ('TRY', 'Turk Lirasi (TRY)'),
            ('USD', 'ABD Dolari (USD)'),
            ('EUR', 'Euro (EUR)'),
        ],
        string='Para Birimi',
        default='TRY',
        required=True,
    )
    installment_count = fields.Integer(
        string='Taksit Sayisi',
        default=1,
    )
    installment_amount = fields.Float(
        string='Taksit Tutari',
        digits=(12, 2),
    )
    total_amount = fields.Float(
        string='Toplam Tutar',
        digits=(12, 2),
    )
    interest_amount = fields.Float(
        string='Faiz Tutari',
        digits=(12, 2),
        compute='_compute_interest_amount',
        store=True,
    )

    # ── Card information ───────────────────────────────────────────────
    card_number_masked = fields.Char(
        string='Maskeli Kart Numarasi',
        help='Kart numarasinin maskeli hali (orn: 5456****1234).',
    )
    card_holder_name = fields.Char(
        string='Kart Sahibi',
    )
    card_type = fields.Selection(
        selection=[
            ('visa', 'Visa'),
            ('mastercard', 'Mastercard'),
            ('amex', 'American Express'),
            ('troy', 'Troy'),
            ('other', 'Diger'),
        ],
        string='Kart Tipi',
    )

    # ── State management ───────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Taslak'),
            ('pending', 'Beklemede'),
            ('processing', 'Isleniyor'),
            ('waiting_3d', '3D Bekleniyor'),
            ('success', 'Basarili'),
            ('failed', 'Basarisiz'),
            ('cancelled', 'Iptal Edildi'),
            ('refunded', 'Iade Edildi'),
            ('partial_refund', 'Kismi Iade'),
        ],
        string='Durum',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )

    # ── Bank response fields ───────────────────────────────────────────
    bank_response_code = fields.Char(
        string='Banka Yanit Kodu',
    )
    bank_response_message = fields.Text(
        string='Banka Yanit Mesaji',
    )
    bank_order_id = fields.Char(
        string='Banka Siparis No',
    )
    auth_code = fields.Char(
        string='Otorizasyon Kodu',
    )
    rrn = fields.Char(
        string='RRN (Referans No)',
        help='Retrieval Reference Number.',
    )
    host_ref_num = fields.Char(
        string='Host Referans No',
    )

    # ── 3D Secure fields ──────────────────────────────────────────────
    is_3d_secure = fields.Boolean(
        string='3D Secure',
        default=True,
    )
    threed_status = fields.Char(
        string='3D Durum',
    )
    md_status = fields.Char(
        string='MD Status',
        help='3D Secure MD Status degeri (1=basarili, vs.).',
    )
    eci = fields.Char(
        string='ECI',
        help='Electronic Commerce Indicator.',
    )
    cavv = fields.Char(
        string='CAVV',
        help='Cardholder Authentication Verification Value.',
    )
    xid = fields.Char(
        string='XID',
        help='3D Secure Transaction ID.',
    )

    # ── Technical / debug fields ───────────────────────────────────────
    ip_address = fields.Char(
        string='IP Adresi',
    )
    user_agent = fields.Char(
        string='User Agent',
    )
    request_data = fields.Text(
        string='Istek Verisi',
        help='Gateway\'e gonderilen istek verisi (debug amacli).',
    )
    response_data = fields.Text(
        string='Yanit Verisi',
        help='Gateway\'den alinan yanit verisi (debug amacli).',
    )
    error_message = fields.Text(
        string='Hata Mesaji',
    )
    error_code = fields.Char(
        string='Hata Kodu',
    )

    # ── Refund fields ──────────────────────────────────────────────────
    refunded_amount = fields.Float(
        string='Iade Edilen Tutar',
        digits=(12, 2),
        default=0.0,
    )
    refund_ids = fields.One2many(
        comodel_name='turkish.pos.refund',
        inverse_name='transaction_id',
        string='Iade Kayitlari',
    )
    remaining_refundable = fields.Float(
        string='Iade Edilebilir Tutar',
        compute='_compute_remaining_refundable',
        digits=(12, 2),
    )

    # ── Computed fields ────────────────────────────────────────────────
    @api.depends('total_amount', 'amount')
    def _compute_interest_amount(self):
        for rec in self:
            rec.interest_amount = (rec.total_amount or 0.0) - (rec.amount or 0.0)

    @api.depends('total_amount', 'refunded_amount')
    def _compute_remaining_refundable(self):
        for rec in self:
            rec.remaining_refundable = (rec.total_amount or 0.0) - (rec.refunded_amount or 0.0)

    # ── Actions ────────────────────────────────────────────────────────
    def action_cancel(self):
        """Cancel the transaction (void) if not yet settled."""
        self.ensure_one()
        if self.state not in ('pending', 'processing', 'waiting_3d', 'success'):
            raise UserError(
                _('Sadece beklemede, isleniyor, 3D bekleniyor veya basarili '
                  'islemler iptal edilebilir.')
            )

        _logger.info(
            "Islem iptali baslatiliyor: %s (tutar=%.2f %s)",
            self.transaction_id, self.amount, self.currency,
        )

        try:
            from . import bank_integration
            integration = bank_integration.get_bank_integration(
                self.gateway_id, self.bank_id
            )
            if integration:
                result = integration.cancel(
                    transaction_id=self.transaction_id,
                    bank_order_id=self.bank_order_id,
                    auth_code=self.auth_code,
                    amount=self.total_amount,
                    currency=self.currency,
                )
                if result.get('success'):
                    self.write({
                        'state': 'cancelled',
                        'response_data': str(result),
                    })
                    _logger.info("Islem basariyla iptal edildi: %s", self.transaction_id)
                else:
                    error_msg = result.get('error_message', _('Bilinmeyen hata'))
                    self.write({
                        'error_message': error_msg,
                        'error_code': result.get('error_code', ''),
                        'response_data': str(result),
                    })
                    raise UserError(
                        _('Iptal islemi basarisiz: %s') % error_msg
                    )
            else:
                raise UserError(_('Gateway entegrasyonu bulunamadi.'))
        except UserError:
            raise
        except Exception as e:
            _logger.exception("Islem iptali sirasinda hata: %s", str(e))
            raise UserError(_('Iptal islemi sirasinda hata olustu: %s') % str(e))

    def action_refund(self):
        """Open the refund wizard for this transaction."""
        self.ensure_one()
        if self.state not in ('success', 'partial_refund'):
            raise UserError(
                _('Sadece basarili veya kismi iade edilmis islemler icin iade yapilabilir.')
            )
        if self.remaining_refundable <= 0:
            raise UserError(_('Bu islem icin iade edilebilir tutar kalmamistir.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Iade Islemi'),
            'res_model': 'turkish.pos.refund',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_transaction_id': self.id,
                'default_amount': self.remaining_refundable,
                'default_currency': self.currency,
            },
        }

    def _process_refund(self, amount, reason=None):
        """Process a refund for the given amount.

        :param float amount: Amount to refund.
        :param str reason: Optional refund reason.
        :return: dict with refund result.
        """
        self.ensure_one()
        if amount <= 0:
            raise ValidationError(_('Iade tutari sifirdan buyuk olmalidir.'))
        if amount > self.remaining_refundable:
            raise ValidationError(
                _('Iade tutari (%.2f) iade edilebilir tutardan (%.2f) buyuk olamaz.')
                % (amount, self.remaining_refundable)
            )

        _logger.info(
            "Iade islemi baslatiliyor: %s, tutar=%.2f %s",
            self.transaction_id, amount, self.currency,
        )

        try:
            from . import bank_integration
            integration = bank_integration.get_bank_integration(
                self.gateway_id, self.bank_id
            )
            if not integration:
                raise UserError(_('Gateway entegrasyonu bulunamadi.'))

            result = integration.refund(
                transaction_id=self.transaction_id,
                bank_order_id=self.bank_order_id,
                auth_code=self.auth_code,
                amount=amount,
                currency=self.currency,
            )

            if result.get('success'):
                refund = self.env['turkish.pos.refund'].create({
                    'transaction_id': self.id,
                    'amount': amount,
                    'reason': reason or '',
                    'state': 'success',
                    'bank_response_code': result.get('response_code', ''),
                    'bank_response_message': result.get('response_message', ''),
                })

                new_refunded = self.refunded_amount + amount
                new_state = 'refunded' if new_refunded >= self.total_amount else 'partial_refund'

                self.write({
                    'refunded_amount': new_refunded,
                    'state': new_state,
                })

                _logger.info(
                    "Iade basarili: %s, tutar=%.2f, yeni durum=%s",
                    self.transaction_id, amount, new_state,
                )
                return {'success': True, 'refund_id': refund.id}
            else:
                error_msg = result.get('error_message', _('Bilinmeyen hata'))
                self.env['turkish.pos.refund'].create({
                    'transaction_id': self.id,
                    'amount': amount,
                    'reason': reason or '',
                    'state': 'failed',
                    'bank_response_code': result.get('error_code', ''),
                    'bank_response_message': error_msg,
                })
                return {'success': False, 'error': error_msg}

        except (UserError, ValidationError):
            raise
        except Exception as e:
            _logger.exception("Iade islemi sirasinda hata: %s", str(e))
            raise UserError(_('Iade islemi sirasinda hata olustu: %s') % str(e))

    @api.model
    def _detect_card_type(self, card_number):
        """Detect card type from card number using BIN patterns.

        :param str card_number: Full or partial card number.
        :return: str - card type code (visa, mastercard, amex, troy, other).
        """
        if not card_number:
            return 'other'

        clean = re.sub(r'\D', '', str(card_number))
        if not clean:
            return 'other'

        # Troy: starts with 9792
        if clean.startswith('9792'):
            return 'troy'
        # American Express: starts with 34 or 37
        if clean[:2] in ('34', '37'):
            return 'amex'
        # Mastercard: starts with 51-55 or 2221-2720
        if clean[:2] in ('51', '52', '53', '54', '55'):
            return 'mastercard'
        if len(clean) >= 4:
            mc_range = int(clean[:4])
            if 2221 <= mc_range <= 2720:
                return 'mastercard'
        # Visa: starts with 4
        if clean.startswith('4'):
            return 'visa'

        return 'other'

    @api.model
    def _mask_card_number(self, card_number):
        """Mask a card number keeping first 6 and last 4 digits.

        :param str card_number: Full card number.
        :return: str - masked card number (e.g., '545616******1234').
        """
        if not card_number:
            return ''
        clean = re.sub(r'\D', '', str(card_number))
        if len(clean) < 10:
            return '*' * len(clean)
        return clean[:6] + '*' * (len(clean) - 10) + clean[-4:]


class TurkishPosRefund(models.Model):
    _name = 'turkish.pos.refund'
    _description = 'Sanal POS Iade Kayitlari'
    _order = 'create_date desc'

    transaction_id = fields.Many2one(
        comodel_name='turkish.pos.transaction',
        string='Orijinal Islem',
        required=True,
        ondelete='cascade',
    )
    amount = fields.Float(
        string='Iade Tutari',
        digits=(12, 2),
        required=True,
    )
    reason = fields.Text(
        string='Iade Nedeni',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Taslak'),
            ('pending', 'Beklemede'),
            ('success', 'Basarili'),
            ('failed', 'Basarisiz'),
        ],
        string='Durum',
        default='draft',
        required=True,
    )
    bank_response_code = fields.Char(
        string='Banka Yanit Kodu',
    )
    bank_response_message = fields.Text(
        string='Banka Yanit Mesaji',
    )
    refund_transaction_id = fields.Char(
        string='Iade Islem ID',
    )

    def action_process_refund(self):
        """Process the refund through the bank gateway."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Sadece taslak durumdaki iadeler islenebilir.'))

        self.write({'state': 'pending'})
        result = self.transaction_id._process_refund(
            self.amount, self.reason,
        )
        return result
