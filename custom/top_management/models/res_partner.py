# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError

from odoo.tools.translate import _

from datetime import timedelta
from odoo.osv import expression
from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api

from odoo.exceptions import ValidationError


class Partner(models.Model):
    _inherit = 'res.partner'

    start_date = fields.Date(
        string='Fecha Inicio del cargo', readonly=False)
    end_date = fields.Date(string='Fecha de Finalización cargo', readonly=False)
    employee_ids = fields.One2many(inverse_name='partner_id')
        # business_name=fields.Char(string='Razón Social', help='Denominación Social de la Empresa', required=True)
    # # Datos de Constitución
    # initial_street=fields.Char(string='Domicilio de Constitución')
    # duration=fields.Char(string='Duración')
    # registration_code=fields.Integer(string='Número de Registro', help='Número de Registro Público')
     # campos computados
    def _compute_account_share_count(self):
        # retrieve all children partners and prefetch 'parent_id' on them
        all_partners = self.with_context(active_test=False).search([('id', 'child_of', self.ids)])
        all_partners.read(['parent_id'])
        purchase_order_groups = self.env['account.share']._read_group(
            domain=[('partner_id', 'in', all_partners.ids)],
            fields=['partner_id'], groupby=['partner_id']
        )
        partners = self.browse()
        for group in purchase_order_groups:
            partner = self.browse(group['partner_id'][0])
            while partner:
                if partner in self:
                    partner.account_share_count += group['partner_id_count']
                    partners |= partner
                partner = partner.parent_id
        (self - partners).account_share_count = 0

    @api.depends('shares')
    def _shared_total(self):
        self.total_shared = 0
        if not self.ids:
            return True
        all_partners_and_children = {}
        all_partner_ids = []
        for partner in self.filtered('id'):
            # price_total is in the company currency
            all_partners_and_children[partner] = self.with_context(active_test=False).search([('id', 'child_of', partner.id)]).ids
            all_partner_ids += all_partners_and_children[partner]

        domain = [
            ('partner_id', 'in', all_partner_ids),
            ('state', 'not in', ['draft', 'canceled']),
        ]
        price_totals = self.env['account.share'].read_group(domain, ['price'], ['partner_id'])
        for partner, child_ids in all_partners_and_children.items():
            partner.total_shared = sum(price['price'] for price in price_totals if price['partner_id'][0] in child_ids)
    
    
    account_share_count = fields.Integer(compute='_compute_account_share_count', string='Acciones')
    total_shared = fields.Monetary(compute='_shared_total', string="Aportes",
        groups='account_financial_policies.account_financial_policies_stock_market_group_manager,account_financial_policies.account_financial_policies_group_manager')
    
    def action_view_partner_shares(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account_share_management.account_share_action")
        all_child = self.with_context(active_test=False).search([('id', 'child_of', self.ids)])
        action['domain'] = [
            ('partner_id', 'in', all_child.ids)
        ]
        return action