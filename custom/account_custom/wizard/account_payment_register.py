# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import frozendict


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    partner_type = fields.Selection(selection_add=[
        ('shareholder', 'Accionista'),
    ])
    partner_id = fields.Many2one('res.partner',
        string="Customer/Vendor/Shareholder")
    