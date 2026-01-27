# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class TurkishPosBank(models.Model):
    _name = 'turkish.pos.bank'
    _description = 'Sanal POS Banka Tanimlari'
    _order = 'sequence, name'

    name = fields.Char(
        string='Banka Adi',
        required=True,
        translate=True,
    )
    code = fields.Char(
        string='Banka Kodu',
        required=True,
        help='Benzersiz banka tanimlama kodu (orn: akbank, garanti, isbank).',
    )
    swift_code = fields.Char(
        string='SWIFT Kodu',
        help='Bankanin SWIFT/BIC kodu.',
    )
    sequence = fields.Integer(
        string='Sira',
        default=10,
    )
    active = fields.Boolean(
        string='Aktif',
        default=True,
    )
    gateway_ids = fields.Many2many(
        comodel_name='turkish.pos.gateway',
        relation='turkish_pos_bank_gateway_rel',
        column1='bank_id',
        column2='gateway_id',
        string='Gateway\'ler',
        help='Bu bankanin calisdigi sanal POS gateway tanimlari.',
    )
    payment_model = fields.Selection(
        selection=[
            ('3d_secure', '3D Secure'),
            ('3d_pay', '3D Pay'),
            ('3d_host', '3D Host'),
            ('non_secure', 'Non-Secure (3D\'siz)'),
        ],
        string='Odeme Modeli',
        default='3d_secure',
        help='Bu banka icin varsayilan odeme guvenlik modeli.',
    )
    is_default = fields.Boolean(
        string='Varsayilan',
        default=False,
        help='Pesin (tek cekim) odemeler icin varsayilan banka.',
    )
    country = fields.Char(
        string='Ulke',
        default='Turkiye',
    )
    card_brands = fields.Char(
        string='Markalar',
        help='Bu bankanin destekledigi kart markalari (orn: Axess, Bonus, Maximum, World).',
    )
    logo = fields.Binary(
        string='Banka Logosu',
        attachment=True,
    )
    installment_config_ids = fields.One2many(
        comodel_name='turkish.pos.installment.config',
        inverse_name='bank_id',
        string='Taksit Ayarlari',
    )
    category_restriction_ids = fields.One2many(
        comodel_name='turkish.pos.category.restriction',
        inverse_name='bank_id',
        string='Kategori Kisitlamalari',
    )
    # Computed fields
    installment_count = fields.Integer(
        string='Taksit Secenegi Sayisi',
        compute='_compute_installment_count',
    )
    color = fields.Integer(
        string='Renk Indeksi',
        default=0,
    )

    _sql_constraints = [
        ('unique_code', 'UNIQUE(code)',
         'Bu banka kodu zaten tanimli! Her banka kodu benzersiz olmalidir.'),
    ]

    @api.depends('installment_config_ids')
    def _compute_installment_count(self):
        for rec in self:
            rec.installment_count = len(rec.installment_config_ids.filtered('active'))

    def get_active_installments(self):
        """Return active installment configurations for this bank."""
        self.ensure_one()
        return self.installment_config_ids.filtered(lambda c: c.active)

    def get_installment_for_amount(self, amount, category_id=None):
        """Return available installment options for a given amount and optional category.

        :param float amount: The payment amount.
        :param int category_id: Optional product.public.category ID for restriction lookup.
        :return: list of dicts with installment details.
        """
        self.ensure_one()
        result = []
        active_configs = self.get_active_installments()

        # Apply category restrictions if category provided
        max_installment = 36
        if category_id:
            restriction = self.category_restriction_ids.filtered(
                lambda r: r.category_id.id == category_id and r.installment_allowed
            )
            if restriction:
                restriction = restriction[0]
                max_installment = restriction.max_installment
                blocked = restriction.get_blocked_installment_list()
            else:
                blocked = []
        else:
            blocked = []

        for config in active_configs:
            if config.installment_count > max_installment:
                continue
            if config.installment_count in blocked:
                continue
            if config.min_amount and amount < config.min_amount:
                continue

            installment_data = config.calculate_installment(amount)
            result.append(installment_data)

        return sorted(result, key=lambda x: x.get('installment_count', 0))

    def action_view_installments(self):
        """Open installment configurations for this bank."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('%s - Taksit Ayarlari') % self.name,
            'res_model': 'turkish.pos.installment.config',
            'view_mode': 'list,form',
            'domain': [('bank_id', '=', self.id)],
            'context': dict(self.env.context, default_bank_id=self.id),
        }
