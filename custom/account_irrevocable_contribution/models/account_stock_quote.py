# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from functools import lru_cache


from odoo.exceptions import UserError

from datetime import datetime, timedelta

from odoo.osv import expression
from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api, tools, _

from odoo.osv.expression import get_unaccent_wrapper

from odoo.exceptions import ValidationError

from odoo.addons.base.models.res_partner import _tz_get

from odoo.tools.translate import _

from odoo.exceptions import UserError, AccessError


class AccountStockQuote(models.Model):
    _name = 'account.stock.quote'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Stock quote'
    _order = 'date desc'
    _rec_name = 'date'

    # campos computados
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            args = args or []
            domain = [('state','=','new')]
            return self.search(expression.AND([domain, args]), limit=limit).name_get()
        
    def name_get(self):
        result = []
        for ast in self:
            name = '%s - (%s)' % (ast.name, ast.date)
            result.append((ast.id, name))
        return result
    
    name=fields.Char(string='Name')
    date=fields.Date(string='Date', help='Date for Stock Quote')
    price=fields.Monetary(string='Price',help='listing price', company_currency_id='company_currency_id')

    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company.id)
    company_currency_id = fields.Many2one(
        string='Company Currency',
        related='company_id.currency_id', readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        tracking=True,
        required=True,
        store=True, readonly=False, precompute=True,
    )