# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = ['res.config.settings']

    # IO fields
    lock_confirmed_io = fields.Boolean(
        "Lock Confirmed Orders", default=lambda self: self.env.company.io_lock == 'lock')
    io_double_validation = fields.Selection(
        related='company_id.io_double_validation', string="Levels of Approvals *", readonly=False)
    io_double_validation_amount = fields.Monetary(
        related='company_id.io_double_validation_amount', string="Minimum Amount", currency_field='company_currency_id', readonly=False)
    io_lock = fields.Selection(related='company_id.io_lock',
                               string="Purchase Order Modification *", readonly=False)
    io_order_approval = fields.Boolean(
        "Purchase Order Approval", default=lambda self: self.env.company.io_double_validation == 'two_step')

