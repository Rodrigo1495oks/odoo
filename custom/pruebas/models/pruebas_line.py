# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from bisect import bisect_left
from collections import defaultdict
import re

class TestLine(models.Model):
    _name = "custom.test.line"
    _inherit = ['mail.thread']
    _description = "Model for test line"
    _order = "name desc"
    _check_company_auto = True
    _rec_name='short_name'

    name=fields.Char(string='Name', index=True, size=32)
    short_name=fields.Char(string='Referencia', )

    order_id=fields.Many2one(string='order Test', comodel_name='custom.test', store=True, index=True)

    amount=fields.Float(string='Monto', default=0.0)



class Test(models.Model):
    _name = "custom.test"
    _inherit = ['custom.test']

    line_ids=fields.One2many(string='Lines', comodel_name='custom.test.line', inverse_name='order_id', store=True)