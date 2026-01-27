# -*- coding: utf-8 -*-

import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TurkishPosGateway(models.Model):
    _name = 'turkish.pos.gateway'
    _description = 'Sanal POS Gateway Tanimlari'
    _order = 'sequence, name'

    name = fields.Char(
        string='Gateway Adi',
        required=True,
        translate=True,
    )
    code = fields.Selection(
        selection=[
            ('param', 'Param (Turk POS)'),
            ('tosla', 'Tosla (Akbank Fintek)'),
            ('iyzico', 'iyzico'),
            ('qnbpay', 'QNB Pay'),
            ('akbank_pos', 'Akbank Sanal POS'),
            ('estv3_pos', 'EST V3 (Asseco / Payten)'),
            ('garanti_pos', 'Garanti BBVA Sanal POS'),
            ('posnet', 'Posnet (Yapi Kredi)'),
            ('payfor', 'PayFor (Finansbank)'),
            ('payflex_mpi', 'PayFlex MPI (Vakifbank / Ziraat)'),
            ('interpos', 'InterPOS (Denizbank)'),
            ('kuveyt_pos', 'Kuveyt Turk Sanal POS'),
        ],
        string='Gateway Kodu',
        required=True,
    )
    sequence = fields.Integer(
        string='Sira',
        default=10,
    )
    active = fields.Boolean(
        string='Aktif',
        default=True,
    )
    description = fields.Text(
        string='Aciklama',
        translate=True,
    )
    supports_all_banks = fields.Boolean(
        string='Tum Bankalari Destekler',
        default=False,
        help='Isaretlenirse, bu gateway tum bankalar ile calisabilir.',
    )
    credentials = fields.Text(
        string='Kimlik Bilgileri (JSON)',
        help='JSON formatinda kimlik bilgileri. Ornek: '
             '{"clientCode": "10738", "username": "Test", '
             '"password": "Test", "guid": "0c13d406-873b-403b-9c09-a5766840d98c"}',
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
        help='Kullanilacak odeme guvenlik modeli.',
    )
    environment = fields.Selection(
        selection=[
            ('test', 'Test'),
            ('production', 'Uretim (Production)'),
        ],
        string='Ortam',
        default='test',
    )
    bank_ids = fields.One2many(
        comodel_name='turkish.pos.bank',
        compute='_compute_bank_ids',
        string='Bankalar',
    )
    bank_count = fields.Integer(
        string='Banka Sayisi',
        compute='_compute_bank_count',
    )

    _sql_constraints = [
        ('unique_code', 'UNIQUE(code)',
         'Bu gateway kodu zaten tanimli! Her gateway kodu benzersiz olmalidir.'),
    ]

    @api.depends()
    def _compute_bank_ids(self):
        """Compute banks related to this gateway via Many2many."""
        for rec in self:
            rec.bank_ids = self.env['turkish.pos.bank'].search([
                ('gateway_ids', 'in', rec.id),
            ])

    @api.depends('bank_ids')
    def _compute_bank_count(self):
        for rec in self:
            rec.bank_count = len(rec.bank_ids)

    def get_credentials(self):
        """Parse and return credentials as a dictionary."""
        self.ensure_one()
        if not self.credentials:
            return {}
        try:
            return json.loads(self.credentials)
        except (json.JSONDecodeError, TypeError) as e:
            _logger.error(
                "Gateway %s icin kimlik bilgileri JSON parse hatasi: %s",
                self.name, str(e),
            )
            raise ValidationError(
                _("Gateway '%s' icin kimlik bilgileri gecerli bir JSON formatinda degil.") % self.name
            ) from e

    def action_view_banks(self):
        """Open the list of banks linked to this gateway."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bankalar'),
            'res_model': 'turkish.pos.bank',
            'view_mode': 'list,form',
            'domain': [('gateway_ids', 'in', self.id)],
            'context': dict(self.env.context),
        }

    def action_test_connection(self):
        """Test the connection to the gateway with current credentials."""
        self.ensure_one()
        try:
            from . import bank_integration
            integration = bank_integration.get_bank_integration(self, None)
            if integration:
                _logger.info(
                    "Gateway %s (%s) baglanti testi baslatiliyor...",
                    self.name, self.code,
                )
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Baglanti Testi'),
                        'message': _('Gateway baglantisi basariyla kuruldu.'),
                        'type': 'success',
                        'sticky': False,
                    },
                }
        except Exception as e:
            _logger.error(
                "Gateway %s baglanti testi basarisiz: %s",
                self.name, str(e),
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Baglanti Testi Basarisiz'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                },
            }
