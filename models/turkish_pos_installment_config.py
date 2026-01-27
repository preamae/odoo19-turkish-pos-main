# -*- coding: utf-8 -*-

import logging
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TurkishPosInstallmentConfig(models.Model):
    _name = 'turkish.pos.installment.config'
    _description = 'Banka Taksit Ayarlari'
    _order = 'bank_id, installment_count'

    bank_id = fields.Many2one(
        comodel_name='turkish.pos.bank',
        string='Banka',
        required=True,
        ondelete='cascade',
    )
    installment_count = fields.Integer(
        string='Taksit Sayisi',
        required=True,
        help='Taksit adedi (1 = pesin, 2-36 arasi taksit).',
    )
    interest_rate = fields.Float(
        string='Faiz Orani (%)',
        digits=(5, 2),
        default=0.0,
        help='Taksit faiz orani yuzde olarak.',
    )
    commission_rate = fields.Float(
        string='Komisyon Orani (%)',
        digits=(5, 2),
        default=0.0,
        help='Banka komisyon orani yuzde olarak.',
    )
    active = fields.Boolean(
        string='Aktif',
        default=True,
    )
    min_amount = fields.Float(
        string='Minimum Tutar',
        digits=(12, 2),
        default=0.0,
        help='Bu taksit secenegi icin minimum siparis tutari.',
    )
    # Campaign fields
    campaign_active = fields.Boolean(
        string='Kampanya Aktif',
        default=False,
        help='Isaretlenirse kampanya orani uygulanir.',
    )
    campaign_rate = fields.Float(
        string='Kampanya Orani (%)',
        digits=(5, 2),
        default=0.0,
        help='Kampanya doneminde uygulanacak ozel faiz orani.',
    )
    campaign_start_date = fields.Date(
        string='Kampanya Baslangic Tarihi',
    )
    campaign_end_date = fields.Date(
        string='Kampanya Bitis Tarihi',
    )
    # Computed display fields
    effective_rate = fields.Float(
        string='Gecerli Oran (%)',
        compute='_compute_effective_rate',
        digits=(5, 2),
    )

    _sql_constraints = [
        ('unique_bank_installment', 'UNIQUE(bank_id, installment_count)',
         'Bu banka icin ayni taksit sayisi zaten tanimli!'),
    ]

    @api.constrains('installment_count')
    def _check_installment_count(self):
        for rec in self:
            if rec.installment_count < 1 or rec.installment_count > 36:
                raise ValidationError(
                    _('Taksit sayisi 1 ile 36 arasinda olmalidir.')
                )

    @api.constrains('campaign_start_date', 'campaign_end_date')
    def _check_campaign_dates(self):
        for rec in self:
            if rec.campaign_active and rec.campaign_start_date and rec.campaign_end_date:
                if rec.campaign_start_date > rec.campaign_end_date:
                    raise ValidationError(
                        _('Kampanya baslangic tarihi bitis tarihinden sonra olamaz.')
                    )

    @api.depends('interest_rate', 'campaign_active', 'campaign_rate',
                 'campaign_start_date', 'campaign_end_date')
    def _compute_effective_rate(self):
        for rec in self:
            rec.effective_rate = rec.get_effective_rate()

    def get_effective_rate(self):
        """Return the effective interest rate, considering active campaigns.

        If a campaign is active and within valid dates, use campaign_rate;
        otherwise fall back to the standard interest_rate.

        :return: float - the applicable interest rate.
        """
        self.ensure_one()
        if self.campaign_active:
            today = date.today()
            start_ok = not self.campaign_start_date or self.campaign_start_date <= today
            end_ok = not self.campaign_end_date or self.campaign_end_date >= today
            if start_ok and end_ok:
                _logger.debug(
                    "Banka %s, %d taksit icin kampanya orani uygulaniyor: %%%.2f",
                    self.bank_id.name, self.installment_count, self.campaign_rate,
                )
                return self.campaign_rate
        return self.interest_rate

    def calculate_installment(self, amount):
        """Calculate installment breakdown for a given amount.

        :param float amount: The base payment amount.
        :return: dict with installment calculation details.
        """
        self.ensure_one()
        rate = self.get_effective_rate()
        interest_amount = amount * (rate / 100.0)
        total_amount = amount + interest_amount

        if self.installment_count > 0:
            installment_amount = total_amount / self.installment_count
        else:
            installment_amount = total_amount

        result = {
            'config_id': self.id,
            'bank_id': self.bank_id.id,
            'bank_name': self.bank_id.name,
            'bank_code': self.bank_id.code,
            'installment_count': self.installment_count,
            'interest_rate': rate,
            'commission_rate': self.commission_rate,
            'base_amount': round(amount, 2),
            'interest_amount': round(interest_amount, 2),
            'total_amount': round(total_amount, 2),
            'installment_amount': round(installment_amount, 2),
            'is_campaign': self.campaign_active and rate == self.campaign_rate,
        }

        _logger.debug(
            "Taksit hesaplama: %s, %d taksit, tutar=%.2f, toplam=%.2f",
            self.bank_id.name, self.installment_count, amount, total_amount,
        )

        return result
