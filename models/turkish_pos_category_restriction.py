# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TurkishPosCategoryRestriction(models.Model):
    _name = 'turkish.pos.category.restriction'
    _description = 'Kategori Bazli Taksit Kisitlamalari'
    _order = 'bank_id, category_id'

    bank_id = fields.Many2one(
        comodel_name='turkish.pos.bank',
        string='Banka',
        required=True,
        ondelete='cascade',
    )
    category_id = fields.Many2one(
        comodel_name='product.public.category',
        string='Urun Kategorisi',
        required=True,
        ondelete='cascade',
    )
    max_installment = fields.Integer(
        string='Maksimum Taksit',
        default=12,
        help='Bu kategori icin izin verilen maksimum taksit sayisi.',
    )
    min_installment = fields.Integer(
        string='Minimum Taksit',
        default=2,
        help='Bu kategori icin izin verilen minimum taksit sayisi.',
    )
    installment_allowed = fields.Boolean(
        string='Taksit Izni',
        default=True,
        help='Isaretli degilse bu kategori icin taksit secenegi sunulmaz.',
    )
    blocked_installments = fields.Char(
        string='Engelli Taksitler',
        help='Virgul ile ayrilmis engelli taksit sayilari (orn: 5,7,11).',
    )

    _sql_constraints = [
        ('unique_bank_category', 'UNIQUE(bank_id, category_id)',
         'Bu banka ve kategori kombinasyonu icin zaten bir kisitlama tanimli!'),
    ]

    @api.constrains('min_installment', 'max_installment')
    def _check_installment_range(self):
        for rec in self:
            if rec.min_installment < 1:
                raise ValidationError(
                    _('Minimum taksit sayisi en az 1 olmalidir.')
                )
            if rec.max_installment < rec.min_installment:
                raise ValidationError(
                    _('Maksimum taksit sayisi minimum taksit sayisindan kucuk olamaz.')
                )
            if rec.max_installment > 36:
                raise ValidationError(
                    _('Maksimum taksit sayisi 36\'dan buyuk olamaz.')
                )

    def get_blocked_installment_list(self):
        """Parse the blocked_installments field and return a list of integers.

        :return: list of int - blocked installment counts.
        """
        self.ensure_one()
        if not self.blocked_installments:
            return []
        try:
            parts = self.blocked_installments.replace(' ', '').split(',')
            blocked = [int(p) for p in parts if p.strip().isdigit()]
            return blocked
        except (ValueError, AttributeError) as e:
            _logger.warning(
                "Engelli taksit listesi parse hatasi (bank=%s, category=%s): %s",
                self.bank_id.name, self.category_id.name, str(e),
            )
            return []

    def get_allowed_installments(self, available_installments):
        """Filter available installments based on this restriction.

        :param list available_installments: List of installment count integers
            that are generally available.
        :return: list of int - filtered installment counts allowed for this
            bank/category combination.
        """
        self.ensure_one()

        if not self.installment_allowed:
            _logger.debug(
                "Taksit izni yok: bank=%s, category=%s",
                self.bank_id.name, self.category_id.name,
            )
            return [1]  # Only single payment (pesin) allowed

        blocked = self.get_blocked_installment_list()
        allowed = []

        for count in available_installments:
            # Always allow single payment (pesin)
            if count == 1:
                allowed.append(count)
                continue
            # Check range
            if count < self.min_installment:
                continue
            if count > self.max_installment:
                continue
            # Check blocked list
            if count in blocked:
                continue
            allowed.append(count)

        _logger.debug(
            "Izin verilen taksitler: bank=%s, category=%s, result=%s",
            self.bank_id.name, self.category_id.name, allowed,
        )

        return sorted(allowed)
