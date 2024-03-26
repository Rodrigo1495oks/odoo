
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

class SuscriptionOrderLine(models.Model):
    _name = 'account.suscription.order.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # _inherits = {'calendar.event': 'event_id'}
    _description = 'Object Share Subscription Line'
    _order = 'ref desc'
    _rec_name = 'ref'

    order_id = fields.Many2one(string='Suscription Order', comodel_name='account.suscription.order', 
                               index=True, 
                               required=True, 
                               readonly=True, 
                               auto_join=True, 
                               ondelete="cascade",
                               check_company=True,
                               help="The order of this line.")
    # compute methods

    @api.depends('quantity', 'price_unit','currency_id')
    def _compute_totals(self):
        for line in self:
            if line.currency_rate:
                line.price_total=line.quantity*(line.price_unit* line.currency_rate)
            else:
                line.price_total=0

    @api.depends('currency_id', 'company_id', 'date')
    def _compute_currency_rate(self):
        """Funcion para obtener el tipo de cambio"""
        @lru_cache()
        def get_rate(from_currency, to_currency, company, date):
            return self.env['res.currency']._get_conversion_rate(
                from_currency=from_currency,
                to_currency=to_currency,
                company=company,
                date=date,
            )
        for line in self:
            line.currency_rate = get_rate(
                from_currency=line.company_currency_id,
                to_currency=line.currency_id,
                company=line.company_id,
                date=line.order_id.suscription_date or line.date or fields.Date.context_today(line),
            )
    
    line_type=fields.Selection(string='Line Type', selection=[
        ('cash','Cash'),
        ('credit','Credit'),
        ('Product','Product')
    ],required=True)

    company_id = fields.Many2one(
        related='order_id.company_id', store=True, readonly=True, precompute=True,
        index=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        tracking=True, help='Currency of the line amount',
        required=False,
        store=True, readonly=False,
    )
    company_currency_id = fields.Many2one(
        string='Company Currency',
        related='order_id.company_currency_id', readonly=True, store=True, precompute=True,
    )

    date = fields.Date(string='Date',
        related='order_id.date', store=True,
        copy=False,
 
    )
    ref = fields.Char(string='Ref',
        related='order_id.short_name', store=True,
        copy=False,
        index='trigram', readonly=True,
    )


    # ==============================================================================================
    #                                          FOR account_move_line
    # ==============================================================================================

    # Money fields
    description = fields.Char(
        string='Description',
    )

    money_type=fields.Selection(string='Type', selection=[
        ('money','Cash'),
        ('check','Check'),
        ('foreign_currency','Foreign Currency'),
        ('wire_transfer','Wire Transfer')
    ])
    state=fields.Selection(string='State', default='draft', selection=[(
        ('draft','Draft'),
        ('suscribed','Suscribed'),
        ('partial_integrated','Partial Integrated'),
        ('integrated','Integrated'),
        ('canceled','Canceled')
    )])
    # Credit fields
    doc_source=fields.Char(string='Document')
    credit_type=fields.Selection(string='Type',selection=[
        ('will_pay','Pagaré'),
        ('invoice','Invoice'),
        ('other','Other'),
    ],required=False)
    partner_id = fields.Many2one(
        string='Partner', comodel_name='res.partner')
    
    # product or asset fields
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        ondelete='restrict',
    )
    product_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='Unit of Measure',
        store=True, readonly=False, precompute=True,
        domain="[('category_id', '=', product_uom_category_id)]",
        ondelete="restrict",
    )
    product_uom_category_id = fields.Many2one(string='Unit of Measure Cat.',
        comodel_name='uom.category',
        related='product_id.uom_id.category_id',
    )
    quantity = fields.Float(
        string='Quantity',
        store=True, readonly=False,
        digits='Product Unit of Measure',
        help="The optional quantity expressed by this line, eg: number of product sold. "
             "The quantity is not a legal requirement but is very useful for some reports.",
    )
    # Confirm if it' fixed asset
    asset_profile_id = fields.Many2one(
        comodel_name="account.asset.profile",
        string="Asset Profile",
        compute="_compute_asset_profile",
        store=True,
        readonly=False,
    )
    # === Price fields === #
    price_unit = fields.Float(
        string='Unit Price',
        store=True, readonly=False, help='Amount in currency',
        digits='Product Price',
    )

    price_total = fields.Monetary(
        string='Total',
        compute='_compute_totals', help='Total Line in Company Currency',
        store=True, 
        readonly=True,
        currency_field='currency_id',
    )

    currency_rate = fields.Float(
        compute='_compute_currency_rate',
        help="Currency rate from company currency to document currency.",
    )

    qty_integrated=fields.Monetary(string='Qty Integrated', help='Amount of the line that has been integrated', currency_field='currency_id', )
                                #    _compute_qty_integrated
    
class SuscriptionOrder(models.Model):
    _name = 'account.suscription.order'
    _inherit = 'account.suscription.order'
    
    @api.depends('product_lines','cash_lines','credit_lines')
    def _compute_totals(self):
        for order in self:
            cash_total=0
            credit_total=0
            product_total=0

            lines=order.env['account.suscription.order.line'].read_group(domain=[('order_id','=',order.id)],
                            fields=['price_total'],
                            groupby=['line_type'],orderby='date')
            for line in lines:
                print(line)

            order.cash_total=cash_total
            order.credit_total=credit_total
            order.product_total=product_total
            order.amount_total=cash_total+credit_total+product_total

    @api.onchange('amount_total')
    def _onchange_amount_total(self):
        for record in self:
            if record.amount_total<record.price_total:
                return {
                    'warning': {'title': "Warning", 'message': "The total amount of the lines to be subscribed is less than the value of shares to be acquired. Any difference will be compensated in cash", 'type': 'notification'},
    }

    @api.constrains('price_total','product_total','credit_total','cash_total')
    def _check_total_amount(self):
        for rec in self:
            if rec.price_total<(rec.product_total+rec.credit_total+rec.cash_total):
                raise ValidationError(_('The total amount of the lines to be subscribed must coincide with the total of the shares acquired'))
    

    product_lines = fields.One2many(string='Products Lines', comodel_name='account.suscription.order.line.product', 
                                    inverse_name='order_id', domain=[('line_type','=','product')],
                                    copy=False, 
                                    readonly=False,
                                    help='Only Physical Products, no services')
    cash_lines = fields.One2many(string='Cash Lines', comodel_name='account.suscription.order.line.product', 
                                    inverse_name='order_id', domain=[('line_type','=','cash')],
                                    copy=False, 
                                    readonly=False,
                                    help='Only Physical Products, no services')
    credit_lines = fields.One2many(string='Credit Lines', comodel_name='account.suscription.order.line.product', 
                                    inverse_name='order_id', domain=[('line_type','=','credit')],
                                    copy=False, 
                                    readonly=False,
                                    help='Only Physical Products, no services')
    amount_total=fields.Monetary(string='Total', currency_field='company_currency_id',)
    # Total Fields
    cash_total=fields.Monetary(string='Cash Total', store=True, readonly=True,
                                currency_field='company_currency_id', help='Resulting Total of the Cash lines to be subscribed, in company currency')
    credit_total=fields.Monetary(string='Credit Total', store=True, readonly=True,
                                currency_field='company_currency_id', help='Resulting Total of the Credit lines to be subscribed, in company currency')
    product_total=fields.Monetary(string='Product Total', store=True, readonly=True,
                                currency_field='company_currency_id', help='Resulting Total of the Product lines to be subscribed, in company currency')