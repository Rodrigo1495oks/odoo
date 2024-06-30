# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.osv.expression import AND
from dateutil.relativedelta import relativedelta


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    suscription_id = fields.Many2one(
        'account.suscription.order', related='move_ids.suscription_line_id.order_id',
        string="Purchase Orders", readonly=True)

class ReturnPicking(models.TransientModel):
    _inherit = "stock.return.picking"

    def _prepare_move_default_values(self, return_line, new_picking):
        vals = super(ReturnPicking, self)._prepare_move_default_values(return_line, new_picking)
        vals['suscription_line_id'] = return_line.move_id.suscription_line_id.id
        return vals

class Orderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    def action_view_suscription(self):
        """ This function returns an action that display existing
        Suscription orders of given orderpoint.
        """
        result = self.env['ir.actions.act_window']._for_xml_id('account_suscription_order.account_suscription_order_action')

        # Remvove the context since the action basically display RFQ and not PO.
        result['context'] = {}
        order_line_ids = self.env['account.suscription.product.line'].search([('orderpoint_id', '=', self.id)])
        purchase_ids = order_line_ids.mapped('order_id')

        result['domain'] = "[('id','in',%s)]" % (purchase_ids.ids)

        return result

class StockLot(models.Model):
    _inherit = 'stock.lot'

    suscription_order_ids = fields.Many2many('account.suscription.order', string="Purchase Orders", compute='_compute_suscription_order_ids', readonly=True, store=False)
    suscription_order_count = fields.Integer('Suscription order count', compute='_compute_suscription_order_ids')

    @api.depends('name')
    def _compute_suscription_order_ids(self):
        for lot in self:
            stock_moves = self.env['stock.move.line'].search([
                ('lot_id', '=', lot.id),
                ('state', '=', 'done')
            ]).mapped('move_id')
            stock_moves = stock_moves.search([('id', 'in', stock_moves.ids)]).filtered(
                lambda move: move.picking_id.location_id.usage == 'supplier' and move.state == 'done')
            lot.purchase_order_ids = stock_moves.mapped('suscription_line_id.order_id')
            lot.purchase_order_count = len(lot.purchase_order_ids)

    def action_view_so(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account_suscription_order.account_suscription_order_action")
        action['domain'] = [('id', 'in', self.mapped('suscription_order_ids.id'))]
        action['context'] = dict(self._context, create=False)
        return action