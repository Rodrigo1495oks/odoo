# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import operator
import base64
import collections
import hashlib
import re
import pytz
import requests
import math
import babel.dates
import logging
from odoo.exceptions import UserError
from werkzeug import urls

from datetime import datetime, timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api, tools

from odoo.osv.expression import get_unaccent_wrapper, expression

from odoo.addons.base.models.res_partner import _tz_get
from odoo.addons.calendar.models.calendar_attendee import Attendee
from odoo.addons.calendar.models.calendar_recurrence import weekday_to_field, RRULE_TYPE_SELECTION, END_TYPE_SELECTION, \
    MONTH_BY_SELECTION, WEEKDAY_SELECTION, BYDAY_SELECTION
from odoo.tools.translate import _
from odoo.tools.misc import get_lang
from odoo.tools import pycompat, frozendict
from odoo.exceptions import UserError, AccessError, ValidationError


class AccountIrrevocableContribution(models.Model):
    _name = 'account.irrevocable.contribution'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    # _inherits = {'calendar.event': 'event_id'}
    _description = 'Objeto Aporte Irrevocable'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'

    short_name = fields.Char(string='Referencia', default='New',
                             required=True, copy=False, readonly=True)
    name = fields.Char(string='Título', copy=False)
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Urgent')], 'Priority', default='0', index=True)
    date = fields.Date(string='Fecha', required=True,
                       default=fields.datetime.now())
    cont_type = fields.Selection(string='Tipo', help='Escoga el tipo de aporte', selection=[(
        'future', 'Para Futuras Suscripciones'), ('loss', 'Para Absorber Pérdidas Acumuladas')], default='future')

    date_due = fields.Date(string='Fecha Límite de integración', required=True,
                           default=datetime.now() + timedelta(days=90))
    integration_date = fields.Date(
        string='Fecha de Integración', readonly=True)
    user_id = fields.Many2one(
        'res.users', string='Operador', index=True, tracking=True,
        default=lambda self: self.env.user, check_company=True)

    origin = fields.Char(string='Documento Origen')

    share_issuance_id = fields.Many2one(
        string='Emisión', comodel_name='share.issuance', readonly=True, help='Emisión de Acciones Relacionada')

    contribution_count = fields.Integer(string='Cantidad de Asientos', copy=False, default=0, store=True,
                                        compute="_compute_contribution", )
    contribution_ids = fields.Many2many(
        'account.move', string='Asientos', copy=False, store=True)
    integration_count = fields.Integer(
        compute="_compute_integration", string='Cantidad de Asientos', copy=False, default=0, store=True)
    integration_ids = fields.Many2many(
        'account.move', string='Asientos', copy=False, store=True)

    state = fields.Selection(string='State', selection=[
        ('draft', 'Draft'),
        ('new', 'New'),
        ('approved', 'Approved'),
        ('confirm', 'Confirm'),
        ('cancel', 'Cancel')], default='draft')

    # fiscal_position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position',
    #                                      domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    # Pestaña de simulacion
    shares_qty = fields.Integer(string='Qty Shares', default=1)
    nominal_value = fields.Float(related='company_id.share_price', store=True,
                                 string='Issue Value for Shares', required=False, copy=True)
    price = fields.Float(string='Stock Quote', readonly=True,
                         compute='_compute_most_recent_quote')
    total_price = fields.Float(string='Amount to Cont.', default=0.0, compute='_compute_total_price')
    notes = fields.Html(string='Descripción')
    is_public = fields.Boolean(string='Public', help='Public File',
                               groups='account_financial_policies.account_financial_policies_group_manager')
    private_notes = fields.Text(string='Private Notes', groups='account_financial_policies'
                                                               '.account_financial_policies_stock_market_group_manager,'
                                                               'account_financial_policies.account_financial_policies_group_manager')

    # Relational fields
    topic = fields.Many2one(string='Tema de Reunión',
                            comodel_name='assembly.meeting.topic', ondelete='restrict', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company.id)

    partner_id = fields.Many2one(
        string='Shareholder', comodel_name='res.partner', required=True)
    payment_term_id = fields.Many2one(comodel_name='account.payment.term', string='Pay Terms', required=True)

    # === Currency fields === #
    company_currency_id = fields.Many2one(
        string='Company Currency',
        related='company_id.currency_id', readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        tracking=True,
        help='If you choose one currency for the entire order, the import currency for each line will be set to that currency, leave this field empty to set a different currency for each line.',
        required=False,
        store=True, readonly=False,
    )

    # Total tabs

    cash_lines = fields.One2many(string='Cash Lines', comodel_name='account.suscription.cash.line',
                                 inverse_name='contribution_id',
                                 copy=False,
                                 readonly=False,
                                 help='Cash Lines Availables')
    credit_lines = fields.One2many(string='Credit Lines', comodel_name='account.suscription.credit.line',
                                   inverse_name='contribution_id',
                                   copy=False,
                                   readonly=False,
                                   help='Credit Lines Availables')
    product_lines = fields.One2many(string='Product Lines', comodel_name='account.suscription.product.line',
                                    inverse_name='contribution_id',
                                    copy=False,
                                    readonly=False,
                                    help='Product Lines Availables')

    amount_total = fields.Monetary(string='Total', currency_field='company_currency_id', compute='_compute_totals', )
    # Total Fields
    cash_total = fields.Monetary(string='Cash Total', store=True, readonly=True, compute='_compute_totals',
                                 currency_field='company_currency_id',
                                 help='Resulting Total of the Cash lines to be subscribed, in company currency')
    credit_total = fields.Monetary(string='Credit Total', store=True, readonly=True, compute='_compute_totals',
                                   currency_field='company_currency_id',
                                   help='Resulting Total of the Credit lines to be subscribed, in company currency')
    product_total = fields.Monetary(string='Product Total', store=True, readonly=True, compute='_compute_totals',
                                    currency_field='company_currency_id',
                                    help='Resulting Total of the Product lines to be subscribed, in company currency')

    @api.depends('product_lines.date_planned')
    def _compute_date_planned(self):
        """ date_planned = the earliest date_planned across all order lines. """
        for order in self:
            dates_list = order.product_lines.filtered(lambda x: not x.display_type and x.date_planned).mapped(
                'date_planned')
            if dates_list:
                order.date_planned = min(dates_list)
            else:
                order.date_planned = False

    @api.depends('cash_lines', 'credit_lines', 'product_lines')
    def _compute_totals(self):
        if not self.ids:
            return
        for order in self:
            order.cash_total = order.cash_lines.price_total
            order.credit_total = order.credit_lines.price_total
            order.product_total = order.product_lines.price_total
            order.amount_total = order.cash_lines.price_total + \
                                 order.credit_lines.price_total + order.product_lines.price_total

    @api.depends('shares_qty', 'price')
    def _compute_total_price(self):
        for order in self:
            order.total_price = order.shares_qty * order.price

    # campos computations
    @api.depends('integration_ids')
    def _compute_integration(self):
        for order in self:
            invoices = order.mapped('integration_ids')
            order.integration_count = len(invoices)

    @api.depends('contribution_ids')
    def _compute_contribution(self):
        for order in self:
            invoices = order.mapped('contribution_ids')
            order.contribution_count = len(invoices)

    @api.depends('date', 'nominal_value')
    def _compute_most_recent_quote(self):
        for record in self:
            most_recent_quotes = self.env['account.stock.quote'].search(
                domain=[('date' >= record.date - timedelta(days=120))])
            recent_quotes_dict = collections.defaultdict(lambda: 0)
            for quote_id, (date, price) in zip(most_recent_quotes.mapped('id'),
                                               (most_recent_quotes.mapped('date'),
                                                most_recent_quotes.mapped('price'))):
                recent_quotes_dict[quote_id] = (date, price)
            record.price = most_recent_quotes.browse(
                max(recent_quotes_dict.items(), key=operator.itemgetter(1)[:1])[0]).price

    @api.depends('payment_term_id', 'date_order', 'currency_id', 'price_total')
    def _compute_needed_terms(self):
        for invoice in self:
            is_draft = invoice.state == 'draft'  # ver como comprobar el estado del coumento
            invoice.needed_terms = {}
            sign = 1
            if invoice.payment_term_id:
                if is_draft:
                    invoice_payment_terms = invoice.payment_term_id._compute_terms(
                        date_ref=invoice.date_order or fields.Date.today(),
                        currency=invoice.currency_id,
                        tax_amount_currency=0,
                        tax_amount=0,
                        untaxed_amount_currency=invoice.price_total,
                        untaxed_amount=invoice.price_total,
                        company=invoice.company_id,
                        sign=sign
                    )
                    for term in invoice_payment_terms:
                        key = frozendict({
                            'move_id': invoice.id,
                            'date_maturity': fields.Date.to_date(term.get('date')),
                            'discount_date': term.get('discount_date'),
                            'discount_percentage': term.get('discount_percentage'),
                        })
                        values = {
                            'balance': term['company_amount'],
                            'amount_currency': term['foreign_amount'],
                            'discount_amount_currency': term['discount_amount_currency'] or 0.0,
                            'discount_balance': term['discount_balance'] or 0.0,
                            'discount_date': term['discount_date'],
                            'discount_percentage': term['discount_percentage'],
                        }
                        if key not in invoice.needed_terms:
                            invoice.needed_terms[key] = values
                        else:
                            invoice.needed_terms[key]['balance'] += values['balance']
                            invoice.needed_terms[key]['amount_currency'] += values['amount_currency']
                else:
                    invoice.needed_terms[frozendict({
                        'move_id': invoice.id,
                        'date_maturity': fields.Date.to_date(invoice.date_due),
                        'discount_date': False,
                        'discount_percentage': 0
                    })] = {
                        'balance': invoice.price_total,
                        'amount_currency': invoice.price_total,
                    }

    @api.onchange('date_planned')
    def onchange_date_planned(self):
        if self.date_planned:
            self.product_lines.filtered(lambda line: not line.display_type).date_planned = self.date_planned

    @api.onchange('amount_total')
    def _onchange_amount_total(self):
        for record in self:
            if record.amount_total < record.price_total:
                return {
                    'warning': {'title': "Warning",
                                'message': "The total amount of the lines to be subscribed is less than the value of shares to be acquired. Any difference will be compensated in cash",
                                'type': 'notification'},
                }

    def _search_amount_total(self, operator, value):
        operator_map = {
            '>': '<', '>=': '<=',
            '<': '>', '<=': '>=',
        }
        new_op = operator_map.get(operator, operator)
        return [('amount_total', new_op, value)]

    @api.onchange('partner_id', 'company_id')
    def onchange_partner_id(self):
        # Ensures all properties and fiscal positions
        # are taken with the company of the order
        # if not defined, with_company doesn't change anything.
        self = self.with_company(self.company_id)
        default_currency = self._context.get("default_currency_id")
        if not self.partner_id:
            self.currency_id = default_currency or self.env.company.currency_id.id
        else:
            self.payment_term_id = self.partner_id.property_payment_term_id.id
            self.currency_id = default_currency or self.partner_id.currency_id.id or self.env.company.currency_id.id

        cash_pending_partner_ids = self.env['account.suscription.cash.line'].search([
            ('state', '=', 'partial_contributed'),
        ]).mapped('order_id.partner_id')

        credit_pending = self.env['account.suscription.cash.line'].search([
            ('backup_doc', '=', False),
            ('partner_id', '=', self.partner_id.id)
        ], limit=1)
        product_pending = credit_pending = self.env['account.suscription.cash.line'].search([
            ('backup_doc', '=', False),
            ('partner_id', '=', self.partner_id.id)
        ], limit=1)

        if any([self.partner_id.id in cash_pending_partner_ids, len(credit_pending) > 0, len(product_pending) > 0]):
            raise UserWarning(_("The selected contributor registers pending credits"))
        return {}

    @api.constrains('price_total', 'product_total', 'credit_total', 'cash_total')
    def _check_total_price(self):
        for rec in self:
            if rec.total_price < (rec.product_total + rec.credit_total + rec.cash_total):
                raise ValidationError(
                    _('The total amount of the lines to be subscribed must coincide with the total of the shares '
                      'acquired'))

    @api.constrains('date', 'date_due')
    def _check_dates(self):
        for rec in self:
            if rec.date_due and \
                    rec.date_due < rec.date:
                raise ValidationError('Date order Must Be in the past')

    _sql_constraints = [
        ('name_uniq', 'UNIQUE (name)',
         'Order title must be unique.'),
        ('positive_qty', 'CHECK(shares_qty>0)',
         'The number of shares must be positive'),
        ('positive_total', 'CHECK(total_price>=0 AND cash_total>=0 AND credit_total>=0 AND product_total>=0)',
         'The Total Price of shares must be positive')
    ]

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            args = args.copy() or []
            domain = [('state', '=', 'new')]
            if not (name == '' and operator == 'ilike'):
                args += ['|', '|',
                         ('name', operator, name),
                         ('short_name', operator, name),
                         ('partner_id.name', operator, name),
                         ('topic.name', operator, name)]
            return self.search(expression.AND([domain, args]), limit=limit).name_get()

    def name_get(self):
        result = []
        for ast in self:
            name = '%s - (%s)' % (ast.name, ast.date)
            result.append((ast.id, name))
        return result

    # low level methods

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            if 'date' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date']))
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'account.irrevocable.contribution', sequence_date=seq_date) or 'New'
        res = super(AccountIrrevocableContribution, self.create(vals))
        return res

    # Actions
    def action_confirm(self):
        self.ensure_one()
        for issue in self:
            if issue.state == 'draft':
                topic_vals = self._prepare_topic_values()
                self.topic += self.env['assembly.meeting.topic'].create(
                    topic_vals)
                issue.state = 'new'
                return True
            else:
                raise UserError(
                    'Accion no permitida')

    def action_approve(self):
        for cont in self:
            if cont.state not in ['draft', 'cancel', 'confirm', 'approved'] & cont.topic.state == 'approved':
                cont.action_create_contribution()
                cont._action_create_share_issuance()
                cont.state = 'approved'
            else:
                raise UserError('Orden de emision no autorizada')

    def action_cancel(self):
        for cont in self:
            if cont.state not in ['draft', 'new', 'cancel'] and cont.topic.id.state == 'refused':
                cont.action_cancel_contribution()
                cont._action_cancel_share_issuance()
                cont.state = 'cancel'
            else:
                raise UserError('No puede cancelarse el aporte')

    def action_integrate(self):
        for cont in self:
            if cont.share_issuance and cont.state == 'approved':
                cont.create_integration()
                cont.state = 'confirm'
            else:
                raise UserError(
                    'No hay orden de emisión asociada al registro')

    def action_draft(self):
        self.ensure_one()
        for issue in self:
            if issue.state != 'draft':
                if issue.state == 'new':
                    issue.state = 'draft'
                    return True
                else:
                    raise UserError(
                        'No se puede cambiar a borrador un fichero que ya esta en marcha')
            else:
                raise UserError(
                    'Accion no permitida')

    # methods

    def action_create_contribution(self):
        """Create the contribution associated to the IC.
        """
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')
        property_account_contribution_credits_id = self.partner_id.property_account_contribution_credits_id or self.company_id.property_account_contribution_credits_id or \
                                                   self.env['account.account'].search([
                                                       ('internal_type', '=', 'contribution_credits')])[0]
        property_account_contribution_id = self.partner_id.property_account_contribution_id or self.company_id.property_account_contribution_id or \
                                           self.env['account.account'].search([
                                               ('internal_type', '=', 'contribution')])[0]
        property_account_contribution_losses_id = self.partner_id.property_account_contribution_losses_id or self.company_id.property_account_contribution_losses_id or \
                                                  self.env['account.account'].search([
                                                      ('internal_type', '=', 'contribution_losses')])[0]

        # 1) Prepare suscription vals and clean-up the section lines
        contribution_vals_list = []
        for order in self:
            if order.state != 'approved':
                continue

            order = order.with_company(order.company_id)
            # Invoice values.
            contribution_vals = order._prepare_contribution()
            # Invoice line values (asset ad product) (keep only necessary sections).

            # NOTA SOBRE LA REGISTRACIÓN DEL APORTE IRREVOCABLE
            """
            Acá hay dos opciones: registrar el pago sin la orden de pago, o registrar la contribución a una
            cuenta de creditos, y registrando el recibo de pago inmediatamente.
            """
            #
            debit_line = {
                'account_id': property_account_contribution_credits_id,
                'debit': self.amount,
                'contribution_order_id': self.id
            }
            if order.type == 'future':
                credit_line = {
                    'account_id': property_account_contribution_id,
                    'credit': self.amount,
                    'contribution_order_id': self.id
                }
            else:
                credit_line = {
                    'account_id': property_account_contribution_losses_id,
                    'credit': self.amount,
                    'contribution_order_id': self.id
                }
            contribution_vals['line_ids'].append(
                (0, 0, debit_line))
            contribution_vals['line_ids'].append(
                (0, 0, credit_line))

            contribution_vals_list.append(contribution_vals)

        # 3) Create invoices.
        SusMoves = self.env['account.move']
        AccountMove = self.env['account.move'].with_context(
            default_move_type='contribution')
        for vals in contribution_vals_list:
            newInv = AccountMove.with_company(
                vals['company_id']).create(vals)
            self.invoice_ids += newInv
            SusMoves |= newInv

        # 4) Some moves might actually be refunds: convert them if the total amount is negative
        # We do this after the moves have been created since we need taxes, etc. to know if the total
        # is actually negative or not
        SusMoves.filtered(lambda m: m.currency_id.round(m.amount_total)
                                    < 0).action_switch_invoice_into_refund_credit_note()

        return self.action_view_contribution(SusMoves)

    def create_integration(self):
        """Create the integration associated to the IC.
        """
        # precision = self.env['decimal.precision'].precision_get(
        #     'Product Unit of Measure')
        property_account_integration_id = self.partner_id.property_account_integration_id or self.company_id.property_account_integration_id or \
                                          self.env['account.account'].search([
                                              ('internal_type', '=', 'equity')])[0]
        property_account_contribution_id = self.partner_id.property_account_contribution_id or self.company_id.property_account_contribution_id or \
                                           self.env['account.account'].search([
                                               ('internal_type', '=', 'contribution')])[0]
        property_account_contribution_losses_id = self.partner_id.property_account_contribution_losses_id or self.company_id.property_account_contribution_losses_id or \
                                                  self.env['account.account'].search([
                                                      ('internal_type', '=', 'contribution_losses')])[0]

        # 1) Prepare suscription vals and clean-up the section lines
        integration_vals_list = []
        for order in self:
            if order.state != 'approved':
                continue

            order = order.with_company(order.company_id)
            # Invoice values.
            integration_vals = order._prepare_integration()
            # Invoice line values (asset ad product) (keep only necessary sections).

            # NOTA SOBRE LA REGISTRACIÓN DEL APORTE IRREVOCABLE
            """
            Acá hay dos opciones: registrar el pago sin la orden de pago, o registrar la contribución a una
            cuenta de creditos, y registrando el recibo de pago inmediatamente.
            """
            #
            if order.type == 'future':
                debit_line = {
                    'account_id': property_account_contribution_id,
                    'debit': self.amount,
                    'contribution_order_id': self.id
                }
            else:
                debit_line = {
                    'account_id': property_account_contribution_losses_id,
                    'debit': self.amount,
                    'contribution_order_id': self.id
                }

            credit_line = {
                'account_id': property_account_integration_id,
                'credit': self.amount,
                'contribution_order_id': self.id
            }
            integration_vals['line_ids'].append(
                (0, 0, debit_line))
            integration_vals['line_ids'].append(
                (0, 0, credit_line))

            integration_vals_list.append(integration_vals)

        # 3) Create invoices.
        SusMoves = self.env['account.move']
        AccountMove = self.env['account.move'].with_context(
            default_move_type='integration')
        for vals in integration_vals_list:
            newInv = AccountMove.with_company(
                vals['company_id']).create(vals)
            self.integration_ids += newInv
            SusMoves |= newInv

        # 4) Some moves might actually be refunds: convert them if the total amount is negative
        # We do this after the moves have been created since we need taxes, etc. to know if the total
        # is actually negative or not
        SusMoves.filtered(lambda m: m.currency_id.round(m.amount_total)
                                    < 0).action_switch_invoice_into_refund_credit_note()

        return self.action_view_integration(SusMoves)

    def action_cancel_contribution(self):
        """Create the contribution 'Cancel' associated to the IC.
        """
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')
        property_account_contribution_credits_id = self.partner_id.property_account_contribution_credits_id or self.company_id.property_account_contribution_credits_id or \
                                                   self.env['account.account'].search([
                                                       ('internal_type', '=', 'contribution_credits')])[0]
        property_account_contribution_id = self.partner_id.property_account_contribution_id or self.company_id.property_account_contribution_id or \
                                           self.env['account.account'].search([
                                               ('internal_type', '=', 'contribution')])[0]
        property_account_contribution_losses_id = self.partner_id.property_account_contribution_losses_id or self.company_id.property_account_contribution_losses_id or \
                                                  self.env['account.account'].search([
                                                      ('internal_type', '=', 'contribution_losses')])[0]
        # 1) Prepare suscription vals and clean-up the section lines
        contribution_vals_list = []
        for order in self:
            if order.state != 'approved':
                continue

            order = order.with_company(order.company_id)
            # Invoice values.
            contribution_vals = order._prepare_contribution()
            # Invoice line values (asset ad product) (keep only necessary sections).
            if order.type == 'future':
                debit_line = {
                    'account_id': property_account_contribution_id,
                    'debit': self.amount,
                    'contribution_order_id': self.id
                }
            else:
                debit_line = {
                    'account_id': property_account_contribution_losses_id,
                    'debit': self.amount,
                    'contribution_order_id': self.id
                }

            credit_line = {
                'account_id': property_account_contribution_credits_id,
                'credit': self.amount,
                'contribution_order_id': self.id
            }
            contribution_vals['line_ids'].append(
                (0, 0, debit_line))
            contribution_vals['line_ids'].append(
                (0, 0, credit_line))

            contribution_vals_list.append(contribution_vals)

        # 3) Create invoices.
        SusMoves = self.env['account.move']
        AccountMove = self.env['account.move'].with_context(
            default_move_type='contribution')
        for vals in contribution_vals_list:
            newInv = AccountMove.with_company(
                vals['company_id']).create(vals)
            self.contribution_ids += newInv
            SusMoves |= newInv

        # 4) Some moves might actually be refunds: convert them if the total amount is negative
        # We do this after the moves have been created since we need taxes, etc. to know if the total
        # is actually negative or not
        SusMoves.filtered(lambda m: m.currency_id.round(m.amount_total)
                                    < 0).action_switch_invoice_into_refund_credit_note()

        return self.action_view_contribution(SusMoves)

    def _action_cancel_share_issuance(self):
        for cont in self:
            if cont.share_issuance:
                cont.share_issuance.action_cancel()
            else:
                return {
                    'warning': {
                        'title': 'Advertencia!',
                        'message': 'No existe Orden de Emisión!'}
                }

    def _prepare_contribution(self):
        """Prepare the dict of values to create the new invoice for a purchase order.
        """
        self.ensure_one()
        move_type = self._context.get('default_move_type', 'contribution')

        partner_invoice = self.env['res.partner'].browse(
            self.partner_id.address_get(['invoice'])['invoice'])
        partner_bank_id = self.partner_id.partner_id.commercial_partner_id.bank_ids.filtered_domain(
            ['|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)])[:1]

        contribution_vals = {
            'ref': self.short_name or '',
            'move_type': move_type,
            'narration': self.notes,
            'invoice_user_id': self.user_id and self.user_id.id or self.env.user.id,
            'partner_id': self.partner_id.id,
            'fiscal_position_id': (
                    self.fiscal_position_id or self.fiscal_position_id._get_fiscal_position(partner_invoice)).id,
            'payment_reference': self.origin or '',
            'partner_bank_id': partner_bank_id.id,
            'invoice_origin': self.name,
            'contribution_id': self.id,
            # 'invoice_payment_term_id': self.payment_term_id.id,
            'line_ids': [],
            'company_id': self.company_id.id,
        }
        return contribution_vals

    def _prepare_integration(self):
        """Prepare the dict of values to create the new invoice for a purchase order.
        """
        self.ensure_one()
        move_type = self._context.get('default_move_type', 'integration')

        partner_invoice = self.env['res.partner'].browse(self.partner_id.address_get(['invoice'])['invoice'])
        partner_bank_id = self.partner_id.commercial_partner_id.bank_ids.filtered_domain(
            ['|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)])[:1]

        invoice_vals = {
            'ref': self.partner_ref or '',
            'contribution_id': self.id,
            'move_type': move_type,
            'narration': self.notes,
            'currency_id': self.currency_id.id,
            'invoice_user_id': self.user_id and self.user_id.id or self.env.user.id,
            'partner_id': partner_invoice.id,
            'fiscal_position_id': (
                    self.fiscal_position_id or self.fiscal_position_id._get_fiscal_position(partner_invoice)).id,
            'payment_reference': self.partner_ref or '',
            'partner_bank_id': partner_bank_id.id,
            'invoice_origin': self.name,
            'invoice_payment_term_id': self.payment_term_id.id,
            'invoice_line_ids': [],
            'line_ids': [],
            'company_id': self.company_id.id,
        }
        return invoice_vals

    def action_view_contribution(self, contribution=False):
        """This function returns an action that display existing  integrations entries of
        given Integration order ids. When only one found, show the integration entries
        immediately.
        """

        if not contribution:
            # Invoice_ids may be filtered depending on the user. To ensure we get all
            # suscriptions related to the suscription order, we read them in sudo to fill the
            # cache.
            self.invalidate_model(['irrevocable_contribution'])
            self.sudo()._read(['irrevocable_contribution'])
            contribution = self.contribution_ids

        result = self.env['ir.actions.act_window']._for_xml_id(
            'higher_authority.action_move_in_contribution_type')
        # choose the view_mode accordingly
        if len(contribution) > 1:
            result['domain'] = [('id', 'in', contribution.ids)]
        elif len(contribution) == 1:
            res = self.env.ref(
                'higher_authority.view_contribution_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in result:
                result['views'] = form_view + \
                                  [(state, view)
                                   for state, view in result['views'] if view != 'form']
            else:
                result['views'] = form_view
            result['res_id'] = contribution.id
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result

    def action_view_integration(self, integration=False):
        """This function returns an action that display existing  integrations entries of
        given Integration order ids. When only one found, show the integration entries
        immediately.
        """

        if not integration:
            # Invoice_ids may be filtered depending on the user. To ensure we get all
            # suscriptions related to the suscription order, we read them in sudo to fill the
            # cache.
            self.invalidate_model(['irrevocable_contribution'])
            self.sudo()._read(['irrevocable_contribution'])
            integration = self.integration_ids

        result = self.env['ir.actions.act_window']._for_xml_id(
            'higher_authority.action_move_in_integration_type')
        # choose the view_mode accordingly
        if len(integration) > 1:
            result['domain'] = [('id', 'in', integration.ids)]
        elif len(integration) == 1:
            res = self.env.ref(
                'higher_authority.view_integration_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in result:
                result['views'] = form_view + \
                                  [(state, view)
                                   for state, view in result['views'] if view != 'form']
            else:
                result['views'] = form_view
            result['res_id'] = integration.id
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result

    def _action_create_share_issuance(self):
        self.ensure_one()
        """Crea la emision de acciones correspondiente para 
            ser tratada por la asamblea, Sin embargo el orden del dia de 
            aprobacion se trata junto con el de aporte.
        """
        vals = {
            'irrevocable_contribution': self.id,
            'name': self.number,
            'makeup_date': fields.Datetime.now(),
            'nominal_value': self.amount,
            'price': self.amount,
            'issue_premium': 0,
            'issue_discount': 0,
            'company_id': self.company_id,
            'partner_id': self.partner_id.id,
        }
        self.env['shares.issuance'].create(vals)
        return True

    def _prepare_topic_values(self):
        self.ensure_one()
        topic_values = {
            "name": "Aporte de Capital. \n",
            "description": "Aporte de Capital",
            "state": "draft",
            "topic_type": "irrevocable",
        }
        return topic_values
