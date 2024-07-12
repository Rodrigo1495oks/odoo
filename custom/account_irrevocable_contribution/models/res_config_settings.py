# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    lock_confirmed_so = fields.Boolean("Lock Confirmed Orders", default=lambda self: self.env.company.so_lock == 'lock')
    so_lock = fields.Selection(related='company_id.so_lock', string="Suscription Order Modification *", readonly=False)
    so_order_approval = fields.Boolean("Suscription Order Approval", default=lambda self: self.env.company.so_double_validation == 'two_step')
    so_double_validation = fields.Selection(related='company_id.so_double_validation', string="Levels of Approvals *", readonly=False)
    so_double_validation_amount = fields.Monetary(related='company_id.so_double_validation_amount', string="Minimum Amount", currency_field='company_currency_id', readonly=False)
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Company Currency", readonly=True)
    default_purchase_method = fields.Selection([
        ('purchase', 'Ordered quantities'),
        ('receive', 'Received quantities'),
        ], string="Bill Control", default_model="product.template",
        help="This default value is applied to any new product created. "
        "This can be changed in the product detail form.", default="receive")
    module_suscription_requisition = fields.Boolean("Suscription Agreements")
    module_suscription_product_matrix = fields.Boolean("Suscription Grid Entry")

    def set_values(self):
        super().set_values()
        so_lock = 'lock' if self.lock_confirmed_so else 'edit'
        so_double_validation = 'two_step' if self.so_order_approval else 'one_step'
        if self.so_lock != so_lock:
            self.so_lock = so_lock
        if self.so_double_validation != so_double_validation:
            self.so_double_validation = so_double_validation