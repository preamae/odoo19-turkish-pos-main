# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ── Turkish POS fields ─────────────────────────────────────────────
    turkish_pos_transaction_ids = fields.One2many(
        comodel_name='turkish.pos.transaction',
        inverse_name='order_id',
        string='POS Islemleri',
    )
    turkish_pos_selected_bank_id = fields.Many2one(
        comodel_name='turkish.pos.bank',
        string='Secilen Banka',
        help='Odeme icin secilen banka.',
    )
    turkish_pos_installment_count = fields.Integer(
        string='Taksit Sayisi',
        default=1,
        help='Secilen taksit sayisi (1 = pesin).',
    )
    turkish_pos_installment_amount = fields.Float(
        string='Taksit Tutari',
        digits=(12, 2),
        compute='_compute_turkish_pos_installment',
        store=True,
    )
    turkish_pos_total_with_interest = fields.Float(
        string='Faizli Toplam Tutar',
        digits=(12, 2),
        compute='_compute_turkish_pos_installment',
        store=True,
    )

    @api.depends('amount_total', 'turkish_pos_selected_bank_id',
                 'turkish_pos_installment_count')
    def _compute_turkish_pos_installment(self):
        for order in self:
            if not order.turkish_pos_selected_bank_id or \
                    order.turkish_pos_installment_count <= 1:
                order.turkish_pos_installment_amount = order.amount_total
                order.turkish_pos_total_with_interest = order.amount_total
                continue

            bank = order.turkish_pos_selected_bank_id
            configs = bank.installment_config_ids.filtered(
                lambda c: c.installment_count == order.turkish_pos_installment_count
                and c.active
            )

            if configs:
                config = configs[0]
                data = config.calculate_installment(order.amount_total)
                order.turkish_pos_installment_amount = data.get(
                    'installment_amount', order.amount_total
                )
                order.turkish_pos_total_with_interest = data.get(
                    'total_amount', order.amount_total
                )
            else:
                order.turkish_pos_installment_amount = order.amount_total
                order.turkish_pos_total_with_interest = order.amount_total

    def get_available_installments(self):
        """Return available installment options considering category restrictions.

        This method aggregates product categories from all order lines,
        applies category-level restrictions per bank, and returns a structured
        list of available banks with their allowed installment options.

        :return: list of dicts with bank and installment data.
        """
        self.ensure_one()

        amount = self.amount_total
        if amount <= 0:
            return []

        # Get active Turkish POS providers
        providers = self.env['payment.provider'].sudo().search([
            ('code', '=', 'turkish_pos'),
            ('state', 'in', ('enabled', 'test')),
        ])

        if not providers:
            return []

        # Collect all active banks
        all_banks = self.env['turkish.pos.bank']
        min_installment_amount = 100.0
        max_global_installment = 12

        for provider in providers:
            all_banks |= provider.turkish_pos_bank_ids.filtered('active')
            min_installment_amount = min(
                min_installment_amount,
                provider.turkish_pos_min_installment_amount,
            )
            max_global_installment = max(
                max_global_installment,
                provider.turkish_pos_max_installment,
            )

        if not all_banks:
            return []

        # Collect product categories from order lines
        categories = self.env['product.public.category']
        product_installment_allowed = True
        product_max_installment = 0

        for line in self.order_line:
            product = line.product_id
            if product and hasattr(product, 'product_tmpl_id'):
                tmpl = product.product_tmpl_id
                if not tmpl.installment_allowed:
                    product_installment_allowed = False
                    break
                if tmpl.max_installment > 0:
                    if product_max_installment == 0:
                        product_max_installment = tmpl.max_installment
                    else:
                        product_max_installment = min(
                            product_max_installment, tmpl.max_installment
                        )
                if hasattr(tmpl, 'public_categ_ids'):
                    categories |= tmpl.public_categ_ids

        # If any product disallows installments, only allow single payment
        if not product_installment_allowed:
            result = []
            for bank in all_banks:
                result.append({
                    'bank_id': bank.id,
                    'bank_name': bank.name,
                    'bank_code': bank.code,
                    'installments': [{
                        'installment_count': 1,
                        'interest_rate': 0.0,
                        'base_amount': round(amount, 2),
                        'interest_amount': 0.0,
                        'total_amount': round(amount, 2),
                        'installment_amount': round(amount, 2),
                        'is_campaign': False,
                    }],
                })
            return result

        # Build result per bank
        result = []
        for bank in all_banks:
            bank_data = {
                'bank_id': bank.id,
                'bank_name': bank.name,
                'bank_code': bank.code,
                'bank_logo': bank.logo,
                'installments': [],
            }

            # Determine maximum installment for this bank considering
            # all product categories in the order
            effective_max = max_global_installment
            if product_max_installment > 0:
                effective_max = min(effective_max, product_max_installment)

            blocked_installments = set()

            for category in categories:
                if not category.installment_allowed:
                    effective_max = 1
                    break

                cat_max = category.get_max_installment_for_bank(bank.id)
                effective_max = min(effective_max, cat_max)

                # Collect blocked installments from category restrictions
                restriction = category.installment_restriction_ids.filtered(
                    lambda r: r.bank_id.id == bank.id
                )
                if restriction:
                    blocked_installments.update(
                        restriction[0].get_blocked_installment_list()
                    )

            # Get installment configs for this bank
            active_configs = bank.get_active_installments()

            for config in active_configs:
                if config.installment_count > effective_max:
                    continue
                if config.installment_count in blocked_installments:
                    continue
                if config.min_amount and amount < config.min_amount:
                    continue
                if amount < min_installment_amount and config.installment_count > 1:
                    continue

                inst_data = config.calculate_installment(amount)
                bank_data['installments'].append(inst_data)

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

        _logger.debug(
            "Siparis %s icin %d banka, toplam taksit secenekleri hazirlandi.",
            self.name, len(result),
        )

        return result

    def action_view_pos_transactions(self):
        """Open Turkish POS transactions for this order."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('POS Islemleri'),
            'res_model': 'turkish.pos.transaction',
            'view_mode': 'list,form',
            'domain': [('order_id', '=', self.id)],
            'context': dict(self.env.context),
        }
