# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

# Color mapping for bank badges
BANK_COLORS = {
    'akbank': '#E30613',
    'garanti': '#00854A',
    'isbank': '#003399',
    'yapikredi': '#004B93',
    'qnb': '#6B2C91',
    'halkbank': '#003B71',
    'vakifbank': '#FFC600',
    'ziraat': '#C8102E',
    'denizbank': '#003DA5',
    'kuveytturk': '#006747',
    'isbankasi': '#003399',
    'finansbank': '#6B2C91',
    'default': '#6c757d',
}


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    installment_allowed = fields.Boolean(
        string='Taksit Izni',
        default=True,
        help='Bu urun icin taksitli odeme secenegi sunulsun mu?',
    )
    max_installment = fields.Integer(
        string='Maksimum Taksit',
        default=0,
        help='Bu urun icin izin verilen maksimum taksit sayisi. '
             '0 = kategori ayarlarini kullan.',
    )
    min_installment_amount = fields.Float(
        string='Minimum Taksit Tutari',
        default=100.0,
        digits=(12, 2),
        help='Taksit secenegi sunulmasi icin minimum tutar (TRY).',
    )

    def _get_installment_display_data(self):
        """Return installment display data for this product.

        Returns a list of bank dicts, each containing installment breakdowns
        suitable for rendering on the product page.

        :return: list of dicts with bank and installment information.
        """
        self.ensure_one()
        try:
            return self._compute_installment_display_data()
        except Exception as e:
            _logger.error("Installment display data error for product %s: %s", self.id, e)
            return []

    def _get_installment_matrix_data(self):
        """Return installment data as a matrix for multi-column table display.

        Returns a dict with 'banks' (column headers) and 'rows' (installment
        count rows), where each row has a 'cells' list aligned with the banks.

        :return: dict with 'banks' and 'rows' keys, or empty dict.
        """
        self.ensure_one()
        try:
            bank_list = self._compute_installment_display_data()
        except Exception as e:
            _logger.error("Installment matrix data error for product %s: %s", self.id, e)
            return {}

        if not bank_list:
            return {}

        # Build bank headers using first card brand for display name
        banks = []
        for bd in bank_list:
            brands_str = (bd.get('card_brands') or '').strip()
            if brands_str:
                # Use first brand (e.g. "Wings, Neo, Tosla, Axess" -> "Axess")
                # Pick the last brand as it's typically the primary card program
                brands = [b.strip() for b in brands_str.split(',') if b.strip()]
                display_name = brands[0] if brands else bd['bank_name']
            else:
                display_name = bd['bank_name']
            banks.append({
                'bank_id': bd['bank_id'],
                'bank_name': bd['bank_name'],
                'display_name': display_name,
                'bank_code': bd['bank_code'],
                'bank_color': bd['bank_color'],
            })

        # Collect all installment counts across banks
        all_counts = set()
        for bd in bank_list:
            for inst in bd['installments']:
                all_counts.add(inst['installment_count'])
        all_counts = sorted(all_counts)

        # Build installment lookup per bank: {bank_id: {count: inst_data}}
        bank_inst_map = {}
        for bd in bank_list:
            inst_map = {}
            for inst in bd['installments']:
                inst_map[inst['installment_count']] = inst
            bank_inst_map[bd['bank_id']] = inst_map

        # Build rows
        rows = []
        for count in all_counts:
            cells = []
            for bd in bank_list:
                inst = bank_inst_map[bd['bank_id']].get(count)
                if inst:
                    cells.append({
                        'available': True,
                        'installment_amount': inst['installment_amount'],
                        'total_amount': inst['total_amount'],
                        'interest_rate': inst['interest_rate'],
                        'is_campaign': inst.get('is_campaign', False),
                    })
                else:
                    cells.append({'available': False})
            rows.append({
                'installment_count': count,
                'cells': cells,
            })

        return {
            'banks': banks,
            'rows': rows,
        }

    def _compute_installment_display_data(self):
        """Internal method that computes installment display data."""
        if not self.installment_allowed:
            return []

        price = self.list_price
        if price <= 0:
            return []

        # Get active banks from the Turkish POS payment providers
        providers = self.env['payment.provider'].sudo().search([
            ('code', '=', 'turkish_pos'),
            ('state', 'in', ('enabled', 'test')),
        ])

        # Collect all active banks across providers
        all_banks = self.env['turkish.pos.bank']
        if providers:
            for provider in providers:
                if provider.turkish_pos_bank_ids:
                    all_banks |= provider.turkish_pos_bank_ids.filtered('active')

        # Fallback: if no banks assigned to providers, get all active banks
        if not all_banks:
            all_banks = self.env['turkish.pos.bank'].sudo().search([
                ('active', '=', True),
            ])

        if not all_banks:
            return []

        # Determine max installment
        max_inst = self.max_installment
        if max_inst <= 0:
            # Use category setting
            if self.public_categ_ids:
                category_max = max(
                    cat.max_installment_global
                    for cat in self.public_categ_ids
                    if cat.installment_allowed
                ) if self.public_categ_ids.filtered('installment_allowed') else 12
                max_inst = category_max
            else:
                max_inst = 12

        result = []
        for bank in all_banks:
            bank_data = {
                'bank_id': bank.id,
                'bank_name': bank.name,
                'bank_code': bank.code,
                'bank_color': self._get_bank_color(bank.code),
                'bank_logo': bank.logo,
                'card_brands': bank.card_brands or '',
                'installments': [],
            }

            # Get category restrictions
            category_ids = self.public_categ_ids.ids
            restricted_max = max_inst
            blocked_installments = []

            for cat_id in category_ids:
                restrictions = bank.category_restriction_ids.filtered(
                    lambda r: r.category_id.id == cat_id
                )
                if restrictions:
                    restriction = restrictions[0]
                    if not restriction.installment_allowed:
                        restricted_max = 1
                        break
                    restricted_max = min(restricted_max, restriction.max_installment)
                    blocked_installments.extend(
                        restriction.get_blocked_installment_list()
                    )

            # Build installment options
            active_configs = bank.get_active_installments()
            for config in active_configs:
                if config.installment_count > restricted_max:
                    continue
                if config.installment_count in blocked_installments:
                    continue
                if config.min_amount and price < config.min_amount:
                    continue
                if price < self.min_installment_amount and config.installment_count > 1:
                    continue

                inst_data = config.calculate_installment(price)
                bank_data['installments'].append(inst_data)

            # Always include single payment
            if not any(
                i['installment_count'] == 1
                for i in bank_data['installments']
            ):
                bank_data['installments'].insert(0, {
                    'installment_count': 1,
                    'interest_rate': 0.0,
                    'base_amount': round(price, 2),
                    'interest_amount': 0.0,
                    'total_amount': round(price, 2),
                    'installment_amount': round(price, 2),
                    'is_campaign': False,
                })

            bank_data['installments'].sort(
                key=lambda x: x.get('installment_count', 0)
            )

            if bank_data['installments']:
                result.append(bank_data)

        return result

    def _get_max_installment_count(self):
        """Return the maximum installment count available for this product.

        Considers both product-level and category-level settings.

        :return: int - maximum installment count, or 0 if none available.
        """
        self.ensure_one()

        if not self.installment_allowed:
            return 0

        max_inst = self.max_installment
        if max_inst <= 0:
            if self.public_categ_ids:
                allowed_cats = self.public_categ_ids.filtered('installment_allowed')
                if allowed_cats:
                    max_inst = max(cat.max_installment_global for cat in allowed_cats)
                else:
                    max_inst = 0
            else:
                max_inst = 12

        return max_inst

    @api.model
    def _get_bank_color(self, bank_code):
        """Return the brand color for a bank based on its code.

        :param str bank_code: The bank code.
        :return: str - hex color code.
        """
        if not bank_code:
            return BANK_COLORS['default']
        return BANK_COLORS.get(bank_code.lower(), BANK_COLORS['default'])
