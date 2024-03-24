
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from functools import lru_cache


from odoo.exceptions import UserError

from datetime import datetime, timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api, tools, _

from odoo.osv.expression import get_unaccent_wrapper

from odoo.exceptions import ValidationError

from odoo.addons.base.models.res_partner import _tz_get

from odoo.tools.translate import _

from odoo.exceptions import UserError, AccessError



class suscriptionOrderLineCash(models.Model):
    _name = 'account.suscription.order.line.asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # _inherits = {'calendar.event': 'event_id'}
    _description = 'Object Share Subscription Line'
    _order = 'ref desc, move_name desc'
    _rec_name = 'ref'

    @api.depends('quantity', 'price_unit','currency_id')
    def _compute_totals(self):
        for line in self:
            if line.price_unit>0 and line.price_unit>0:
                line.price_total=line.price_unit*line.price_unit
            else:
                line.price_total=0
                
    order_id = fields.Many2one(string='Suscription Order', comodel_name='account.suscription.order', 
                               index=True, 
                               required=True, 
                               readonly=True, 
                               auto_join=True, 
                               ondelete="cascade",
                               check_company=True,
                               help="The order of this line.")


    # action methods

    company_id = fields.Many2one(
        related='order_id.company_id', store=True, readonly=True, precompute=True,
        index=True,
    )
    company_currency_id = fields.Many2one(
        string='Company Currency',
        related='order_id.company_currency_id', readonly=False, store=True, precompute=True,
    )
    move_name = fields.Char(
        string='Number',
        related='order_id.name', store=True, readonly=True,
        index='btree'
    )
    parent_state = fields.Selection(related='order_id.state', store=True)
    date = fields.Date(string='Date',
        related='order_id.date', store=True,
        copy=False,
        group_operator='min',
    )
    ref = fields.Char(string='Ref',
        related='order_id.short_name', store=True,
        copy=False,
        index='trigram', readonly=True,
    )


    # ==============================================================================================
    #                                          FOR account_move_line
    # ==============================================================================================



    # === Price fields === #
    price_unit = fields.Float(
        string='Unit Price',
        store=True, readonly=False, precompute=True,
        digits='Product Price',
    )
    price_total = fields.Monetary(
        string='Total',
        compute='_compute_totals', 
        store=True, 
        readonly=True,
        currency_field='currency_id',
    )

class SuscriptionOrder(models.Model):
    _name = 'account.suscription.order'
    _inherit = 'account.suscription.order'
    
    asset_lines = fields.One2many(string='Assets Lines', 
                                  comodel_name='account.suscription.order.line.asset', 
                                  inverse_name='order_id', copy=False, readonly=False,
                                  states={'draft': [('readonly', False)]})