# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from functools import lru_cache
from pytz import timezone, UTC
from markupsafe import Markup
from odoo.exceptions import UserError
from datetime import datetime, timedelta, timezone, time
from odoo.tools.float_utils import float_is_zero, float_compare, float_round
from odoo import models, fields, api, tools, _
from odoo.osv.expression import get_unaccent_wrapper
from odoo.exceptions import ValidationError
from odoo.addons.base.models.res_partner import _tz_get
from odoo.tools.misc import get_lang
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, relativedelta, format_amount, format_date, formatLang, get_lang, \
    groupby
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError


class SoCreditLine(models.Model):
    _name = 'account.suscription.credit.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # _inherits = {'calendar.event': 'event_id'}
    _description = 'Object Share Subscription Credit Line'
    _order = 'short_name,date desc'
    _rec_name = 'short_name'

    short_name = fields.Char(string='Reference', default='New', required=True, copy=False, readonly=True,
                             store=True,
                             index=True)
    sequence=fields.Integer(string='n',default=1)

    order_id = fields.Many2one(string='Suscription Order', comodel_name='account.suscription.order',
                               index=True,
                               required=False,
                               readonly=True,
                               auto_join=True,
                               ondelete="cascade",
                               check_company=True,
                               help="The order of this Cash line.")
    name = fields.Text(string='Name')
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        related='order_id.company_id', store=True, readonly=True,
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
        related='order_id.company_currency_id', readonly=True, store=True,
    )

    date = fields.Date(string='Date',
                       related='order_id.date_order', store=True,
                       copy=False, )
    date_maturity = fields.Date(string='Date Due', related='order_id.date_due',
                                store=True,
                                copy=False, )
    ref = fields.Char(string='Ref',
                      related='order_id.short_name', store=True,
                      copy=False,
                      index='trigram', readonly=True,
                      )
    state = fields.Selection(string='State', default='draft', selection=[
        ('draft', 'Draft'),
        ('partial_contributed', 'Partial Contributed'),
        ('contributed', 'Totally Contributed'),
        ('integrated', 'Integrated'),
        ('canceled', 'Canceled')
    ], compute='_compute_state')
    display_type = fields.Selection(string='Display Type', selection=[
        ('line_section', "Section"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")
    # Credit fields
    doc_source = fields.Char(string='Document')
    credit_type = fields.Selection(string='Type', selection=[
        ('will_pay', 'Pagaré'),
        ('invoice', 'Invoice'),
        ('other', 'Other'),
    ], required=False)

    partner_id = fields.Many2one(
        string='Partner', comodel_name='res.partner', store=True)
    # === Price fields === #
    price_unit = fields.Float(
        string='Unit Price',
        store=True, readonly=False, help='Amount in currency',
        digits='Product Price', default=0.0
    )

    price_total = fields.Monetary(
        string='Total',
        compute='_compute_totals', help='Total Line in Company Currency',
        store=True,
        readonly=True,
        currency_field='currency_id', default=0.0
    )
    amount_integrated = fields.Monetary(string='Credit Integrated', currency_field='company_currency_id', store=True,
                                        compute='_compute_amount_integrated')
    amount_to_integrate = fields.Monetary(string='Credit to Integrate', currency_field='company_currency_id',
                                          store=True, compute='_compute_amount_integrated')
    currency_rate = fields.Float(
        compute='_compute_currency_rate', default=0.0,
        help="Currency rate from company currency to document currency.",
    )

    narration = fields.Html(
        string='Terms and Conditions',
        store=True, readonly=False,
    )

    move_lines_ids = fields.One2many(comodel_name='account.move.line', inverse_name='integration_credit_line_id',
                                     string="Integration Lines",
                                     readonly=True, copy=False,
                                     domain=[('move_id.move_type', '=', 'integration')])
    suscription_line_ids = fields.One2many(comodel_name='account.move.line', inverse_name='suscription_credit_line_id',
                                           string="Suscription Lines",
                                           readonly=True, copy=False,
                                           domain=[('move_id.move_type', '=', 'suscription')])

    def _get_integrated_lines(self):
        self.ensure_one()
        if self._context.get('accrual_entry_date'):
            return self.move_lines_ids.filtered(
                lambda l: l.move_id.date and l.move_id.date <= self._context['accrual_entry_date']
            )
        else:
            return self.move_lines_ids

    @api.depends('move_lines_ids.move_id.state','order_id.state', 'price_total',)
    def _compute_amount_integrated(self):
        """ determines the integrated amount of the cash and credit lines"""
        for line in self:
            if not line.display_type:
                # compute qty_invoiced
                amount = 0.0
                for inv_line in line._get_integrated_lines():
                    if inv_line.move_id.state not in ['cancel'] or inv_line.move_id.payment_state == 'invoicing_legacy':
                        if inv_line.move_id.move_type == 'integration':
                            amount+=inv_line.debit
                line.amount_integrated = amount
                line.amount_to_integrate = line.price_total - line.amount_integrated
            else:
                line.amount_integrated = 0

    @api.depends('amount_integrated', 'amount_to_integrate', 'display_type', 'amount_integrated',
                 'amount_to_integrate')
    def _compute_state(self):
        for line in self:
            if line.display_type:
                line.state='draft'
                continue

            line.state = 'subscribed' if all(
                [len(line.suscription_line_ids) > 0, line.amount_integrated < 1]) else 'draft'
            line.state = 'partial_contributed' if all(
                [len(line.suscription_line_ids) > 0, line.amount_integrated > 0,
                 line.amount_to_integrate > 0]) else 'draft'
            line.state = 'contributed' if all([len(line.suscription_line_ids) > 0, line.amount_integrated > 0,
                                                   line.amount_to_integrate == 0]) else 'draft'

    @api.depends('price_unit', 'currency_id')
    def _compute_totals(self):
        for line in self:
            if not line.display_type:
                if line.currency_rate > 0.0:
                    line.price_total = 1 * (line.price_unit * line.currency_rate)
                else:
                    line.price_total = 0
            else:
                line.price_total = 0

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
            if not line.display_type:
                line.currency_rate = get_rate(
                    from_currency=line.company_currency_id,
                    to_currency=line.currency_id,
                    company=line.company_id,
                    date=line.order_id.date_order or line.date or fields.Date.context_today(line),
                )
            else:
                line.currency_rate=0

    # helpers
    def _prepare_account_move_line(self, move=False,):
        self.ensure_one()
        aml_currency = move and move.currency_id or self.currency_id
        date = move and move.date or fields.Date.today()
        res = {
            'account_id': '',
            'display_type': self.display_type or 'product',
            'name': '%s: %s - %s' % (self.order_id.name, self.name, self.order_id.short_name),
            'quantity': 1,
            'partner_id': self.partner_id,
            'price_unit': self.currency_id._convert(self.price_unit, aml_currency, self.company_id, date, round=False),
            # 'tax_ids': [(6, 0, self.taxes_id.ids)],
            'suscription_cash_line_id': self.id,
            'date_maturity': self.date_maturity,
        }
        return res
    # low level methods

    @api.model
    def create(self, vals):
        if vals.get('short_name', _('New')) == _('New'):
            seq_date = None
            if 'date' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date_order']))
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'account.suscription.credit.line', sequence_date=seq_date) or _('New')
        return super().create(vals)

    @api.model
    def write(self, values):
        lines = self.filtered(lambda l: l.order_id.state == 'contributed')
        if 'price_unit' in values:
            for line in lines:
                line_moves=line.suscription_line_ids.filtered(lambda aml: aml.state not in ('cancel','posted'))
                line_moves.write({'price_unit': line._get_stock_move_price_unit()})
        if 'currency_id' in values:
            line_moves = line.suscription_line_ids.filtered(lambda aml: aml.state not in ('cancel', 'posted'))
            line_moves.write({'currency_id': line.currency_id})
    #
    #  BUSSINESS METHODS
    #
    def _get_stock_move_price_unit(self):
        self.ensure_one()
        order = self.order_id
        price_unit = self.price_unit
        price_unit_prec = self.env['decimal.precision'].precision_get('Product Price')

        if order.currency_id != order.company_id.currency_id:
            price_unit = order.currency_id._convert(
                price_unit, order.company_id.currency_id, self.company_id, self.date_order or fields.Date.today(), round=False)
        return float_round(price_unit, precision_digits=price_unit_prec)