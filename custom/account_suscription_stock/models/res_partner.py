# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta, datetime, time
from collections import defaultdict

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    suscription_line_ids = fields.One2many('account.suscription.product.line', 'partner_id', string="Suscription Product Lines")

    @api.depends('purchase_line_ids','purchase_line_ids')
    def _compute_on_time_rate(self):
        suscription_lines = self.env['account.suscription.product.line'].search([
            ('partner_id', 'in', self.ids),
            ('date_order', '>', fields.Date.today() - timedelta(365)),
            ('qty_received', '!=', 0),
            ('order_id.state', 'in', ['finished'])
        ]).filtered(lambda l: l.product_id.sudo().product_tmpl_id.type != 'service')
        lines_qty_done = defaultdict(lambda: 0)
        moves = self.env['stock.move'].search([
            ('suscription_line_id', 'in', suscription_lines.ids),
            ('state', '=', 'done')]).filtered(lambda m: m.date.date() <= m.suscription_line_id.date_planned.date())
        for move, qty_done in zip(moves, moves.mapped('quantity_done')):
            lines_qty_done[move.suscription_line_id.id] += qty_done
        partner_dict = {}
        for line in suscription_lines:
            on_time, ordered = partner_dict.get(line.partner_id, (0, 0))
            ordered += line.product_uom_qty
            on_time += lines_qty_done[line.id]

        return super(ResPartner, self)._compute_on_time_rate()