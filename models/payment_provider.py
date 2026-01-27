# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('turkish_pos', 'Turkish POS')],
        ondelete={'turkish_pos': 'cascade'},
    )

    # ── Turkish POS specific fields ────────────────────────────────────
    turkish_pos_bank_ids = fields.Many2many(
        comodel_name='turkish.pos.bank',
        relation='payment_provider_turkish_pos_bank_rel',
        column1='provider_id',
        column2='bank_id',
        string='Aktif Bankalar',
        help='Bu odeme saglayicisi icin aktif olan bankalar.',
    )
    turkish_pos_default_bank_id = fields.Many2one(
        comodel_name='turkish.pos.bank',
        string='Varsayilan Banka',
        help='Pesin (tek cekim) odemeler icin varsayilan banka.',
    )
    turkish_pos_show_installments = fields.Boolean(
        string='Taksit Seceneklerini Goster',
        default=True,
        help='Odeme sayfasinda taksit seceneklerini goster.',
    )
    turkish_pos_default_installment = fields.Integer(
        string='Varsayilan Taksit Sayisi',
        default=1,
        help='Varsayilan taksit sayisi (1 = pesin).',
    )
    turkish_pos_max_installment = fields.Integer(
        string='Maksimum Taksit Sayisi',
        default=12,
        help='Sunulacak maksimum taksit sayisi.',
    )
    turkish_pos_min_installment_amount = fields.Float(
        string='Minimum Taksit Tutari',
        default=100.0,
        digits=(12, 2),
        help='Taksit secenegi sunulmasi icin gerekli minimum siparis tutari (TRY).',
    )

    @api.onchange('turkish_pos_bank_ids')
    def _onchange_turkish_pos_bank_ids(self):
        """Reset default bank if it is no longer in the active banks list."""
        if self.turkish_pos_default_bank_id and \
                self.turkish_pos_default_bank_id not in self.turkish_pos_bank_ids:
            self.turkish_pos_default_bank_id = False
            return {
                'warning': {
                    'title': _('Varsayilan Banka Sifirlandi'),
                    'message': _(
                        'Varsayilan banka aktif bankalar listesinden '
                        'cikarildi ve sifirlandi.'
                    ),
                },
            }

    @api.model
    def _get_compatible_providers(self, *args, **kwargs):
        """Override to add Turkish POS provider compatibility checks."""
        providers = super()._get_compatible_providers(*args, **kwargs)

        # Filter out Turkish POS providers that have no active banks configured
        providers = providers.filtered(
            lambda p: p.code != 'turkish_pos' or p.turkish_pos_bank_ids
        )

        return providers

    def _get_default_payment_method_codes(self):
        """Override to add turkish_pos payment method code."""
        self.ensure_one()
        if self.code == 'turkish_pos':
            return ['turkish_pos']
        return super()._get_default_payment_method_codes()

    def _get_turkish_pos_banks_for_amount(self, amount, currency_code='TRY'):
        """Return active banks with their installment options for a given amount.

        :param float amount: Payment amount.
        :param str currency_code: Currency code (default TRY).
        :return: list of dicts with bank and installment data.
        """
        self.ensure_one()
        if self.code != 'turkish_pos':
            return []

        result = []
        for bank in self.turkish_pos_bank_ids.filtered('active'):
            bank_data = {
                'bank_id': bank.id,
                'bank_name': bank.name,
                'bank_code': bank.code,
                'bank_logo': bank.logo,
                'installments': [],
            }

            if self.turkish_pos_show_installments and \
                    amount >= self.turkish_pos_min_installment_amount:
                configs = bank.get_active_installments()
                for config in configs:
                    if config.installment_count > self.turkish_pos_max_installment:
                        continue
                    if config.min_amount and amount < config.min_amount:
                        continue
                    installment_data = config.calculate_installment(amount)
                    bank_data['installments'].append(installment_data)

            # Always include single payment (pesin)
            if not any(
                i['installment_count'] == 1
                for i in bank_data['installments']
            ):
                bank_data['installments'].insert(0, {
                    'installment_count': 1,
                    'interest_rate': 0.0,
                    'base_amount': round(amount, 2),
                    'interest_amount': 0.0,
                    'total_amount': round(amount, 2),
                    'installment_amount': round(amount, 2),
                    'is_campaign': False,
                })

            bank_data['installments'].sort(
                key=lambda x: x.get('installment_count', 0)
            )
            result.append(bank_data)

        return result
