# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools

class AccountMove(models.Model):
    _inherit = "account.move"

    @api.depends('line_ids.account_share_cost_line_id')
    def _compute_origin_sc_count(self):
        for move in self:
            move.account_share_cost_count = len(
                move.line_ids.account_share_cost_line_id.order_id)
    # Costos de emisión de acciones
    account_share_cost_id = fields.Many2one('account.share.cost', store=False, readonly=True,
                                            states={
                                                'draft': [('readonly', False)]},
                                            string='Account Share Cost Order',
                                            help="Auto-complete from a past Account Share Cost order.")

    account_share_cost_count = fields.Integer(
        compute="_compute_origin_sc_count", string='Account Share Cost Order Count')
    
    def action_view_account_share_cost_orders(self):
        """Muestra las suscripciones de accionistas asociadas al asiento"""
        self.ensure_one()
        source_orders = self.line_ids.account_share_cost_order_id
        result = self.env['ir.actions.act_window']._for_xml_id(
            'account_share_management.account_share_cost_form_action')
        if len(source_orders) > 1:
            result['domain'] = [('id', 'in', source_orders.ids)]
        elif len(source_orders) == 1:
            result['views'] = [
                (self.env.ref('account_share_management.account_share_cost_form', False).id, 'form')]
            result['res_id'] = source_orders.id
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result