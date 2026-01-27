# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TurkishPosBin(models.Model):
    _name = 'turkish.pos.bin'
    _description = 'Kart BIN (Bank Identification Number) Tanimlari'
    _order = 'bin_number'

    name = fields.Char(
        string='Kart Adi',
        required=True,
        help='Kart programi adi (orn: Axess, Bonus, Maximum, World).',
    )
    bin_number = fields.Char(
        string='BIN Numarasi',
        required=True,
        size=6,
        help='Kartin ilk 6 hanesi (Bank Identification Number).',
    )
    bank_id = fields.Many2one(
        comodel_name='turkish.pos.bank',
        string='Banka',
        required=True,
        ondelete='cascade',
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
        default='visa',
    )
    card_family = fields.Char(
        string='Kart Ailesi',
        help='Kart ailesi adi (orn: Axess, Bonus, Maximum, World, Paraf).',
    )
    active = fields.Boolean(
        string='Aktif',
        default=True,
    )

    _sql_constraints = [
        ('unique_bin_number', 'UNIQUE(bin_number)',
         'Bu BIN numarasi zaten tanimli! Her BIN numarasi benzersiz olmalidir.'),
    ]

    @api.constrains('bin_number')
    def _check_bin_number(self):
        for rec in self:
            if rec.bin_number:
                if len(rec.bin_number) != 6:
                    raise ValidationError(
                        _('BIN numarasi tam olarak 6 haneli olmalidir.')
                    )
                if not rec.bin_number.isdigit():
                    raise ValidationError(
                        _('BIN numarasi sadece rakamlardan olusmalidir.')
                    )

    @api.model
    def lookup_bin(self, card_number):
        """Look up the bank and card info from the first 6 digits of the card number.

        :param str card_number: Full or partial card number (min 6 digits).
        :return: recordset of turkish.pos.bin or empty recordset.
        """
        if not card_number:
            return self.browse()

        # Clean non-digit characters
        clean_number = ''.join(c for c in str(card_number) if c.isdigit())
        if len(clean_number) < 6:
            _logger.warning("BIN sorgusu icin en az 6 haneli kart numarasi gerekli.")
            return self.browse()

        bin_prefix = clean_number[:6]
        bin_record = self.search([
            ('bin_number', '=', bin_prefix),
            ('active', '=', True),
        ], limit=1)

        if bin_record:
            _logger.debug(
                "BIN %s bulundu: %s (%s)",
                bin_prefix, bin_record.name, bin_record.bank_id.name,
            )
        else:
            _logger.info("BIN %s icin kayit bulunamadi.", bin_prefix)

        return bin_record

    def name_get(self):
        result = []
        for rec in self:
            display = "%s - %s (%s)" % (
                rec.bin_number,
                rec.name,
                rec.bank_id.name if rec.bank_id else _('Bilinmeyen'),
            )
            result.append((rec.id, display))
        return result
