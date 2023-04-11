# -*- coding: utf-8 -*-
from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date, formatLang


class AccountPayment(models.Model):
    _name = "account.payment"
    _inherit= "account.payment"
    
    integration_order_line=fields.One2many(string='Integraciones en Efectivo', comodel_name='integration.order.line', inverse_name='payment_id')