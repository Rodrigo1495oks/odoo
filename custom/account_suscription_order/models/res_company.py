# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

class Company(models.Model):
    _inherit = 'res.company'

    so_lock = fields.Selection([
        ('edit', 'Allow to edit purchase orders'),
        ('lock', 'Confirmed purchase orders are not editable')
        ], string="Suscription Order Modification", default="edit",
        help='Suscription Order Modification used when you want to purchase order editable after confirm')

    so_double_validation = fields.Selection([
        ('one_step', 'Confirm purchase orders in one step'),
        ('two_step', 'Get 2 levels of approvals to confirm a purchase order')
        ], string="Levels of Approvals", default='one_step',
        help="Provide a double validation mechanism for Suscription")

    so_double_validation_amount = fields.Monetary(string='Double validation amount', default=5000,
        help="Minimum amount for which a double validation is required")