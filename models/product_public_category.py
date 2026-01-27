# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class ProductPublicCategory(models.Model):
    _inherit = 'product.public.category'

    installment_restriction_ids = fields.One2many(
        comodel_name='turkish.pos.category.restriction',
        inverse_name='category_id',
        string='Taksit Kisitlamalari',
        help='Bu kategori icin banka bazli taksit kisitlamalari.',
    )
    max_installment_global = fields.Integer(
        string='Genel Maksimum Taksit',
        default=12,
        help='Bu kategori icin tum bankalar genelinde izin verilen '
             'maksimum taksit sayisi.',
    )
    installment_allowed = fields.Boolean(
        string='Taksit Izni',
        default=True,
        help='Bu kategori icin taksitli odeme secenegi sunulsun mu?',
    )

    def get_max_installment_for_bank(self, bank_id):
        """Return the maximum installment count for a specific bank.

        Checks bank-specific restrictions first; if none found, falls back to
        the global max_installment_global setting.

        :param int bank_id: ID of the turkish.pos.bank record.
        :return: int - maximum installment count.
        """
        self.ensure_one()

        if not self.installment_allowed:
            _logger.debug(
                "Kategori %s icin taksit izni yok, sadece pesin.",
                self.name,
            )
            return 1

        # Look for bank-specific restriction
        restriction = self.installment_restriction_ids.filtered(
            lambda r: r.bank_id.id == bank_id
        )

        if restriction:
            restriction = restriction[0]
            if not restriction.installment_allowed:
                _logger.debug(
                    "Kategori %s, banka ID=%d icin taksit izni yok.",
                    self.name, bank_id,
                )
                return 1
            max_inst = restriction.max_installment
            _logger.debug(
                "Kategori %s, banka ID=%d icin maksimum taksit: %d",
                self.name, bank_id, max_inst,
            )
            return max_inst

        # Fall back to global setting
        _logger.debug(
            "Kategori %s, banka ID=%d icin ozel kisitlama yok, "
            "genel maksimum taksit: %d",
            self.name, bank_id, self.max_installment_global,
        )
        return self.max_installment_global

    def get_installment_restrictions_summary(self):
        """Return a summary of installment restrictions for this category.

        :return: list of dicts with bank restriction details.
        """
        self.ensure_one()
        result = []
        for restriction in self.installment_restriction_ids:
            result.append({
                'bank_id': restriction.bank_id.id,
                'bank_name': restriction.bank_id.name,
                'bank_code': restriction.bank_id.code,
                'max_installment': restriction.max_installment,
                'min_installment': restriction.min_installment,
                'installment_allowed': restriction.installment_allowed,
                'blocked_installments': restriction.get_blocked_installment_list(),
            })
        return result
