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
from odoo.tools.misc import frozendict
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError
from dateutil.relativedelta import relativedelta
class SuscriptionOrder(models.Model):
    _name = 'account.suscription.order'
    _inherit = ['mail.thread', 'mail.activity.mixin','portal.mixin',]
    _description = 'Purpose of Share Subscription'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'

    # campos computados
    @api.model
    def _default_order_stage(self):
        Stage=self.env['account.suscription.order.stage']
        return Stage.search([],limit=1)
    

    # metodos computados

    @api.depends('share_qty')
    def _compute_amount_total(self):
        for order in self:
                order.amount_total= order.price * order.share_qty
    @api.depends('company_id')
    def _compute_share_price(self):
        """Look up the latest stock quote"""
        for order in self:
            # Busco la cotizacion más reciente
            recent_quote=order.env['account.stock.quote'].search([()],limit=1,order='date')
            order.price=recent_quote.price if recent_quote else 0

    @api.depends('needed_terms')
    def _compute_invoice_date_due(self):
        today = fields.Date.context_today(self)
        for move in self:
            move.date_due = move.needed_terms and max(
                (k['date_maturity'] for k in move.needed_terms.keys() if k),
                default=False,
            ) or move.date_due or today

    @api.depends('payment_term_id', 'date_order', 'currency_id', 'price_total', 'date_due')
    def _compute_needed_terms(self):
        for invoice in self:
            is_draft = invoice# ver como comprobar el estado del coumento
            invoice.needed_terms = {}
            sign = 1
            if invoice.payment_term_id:
                if is_draft:
                    invoice_payment_terms = invoice.payment_term_id._compute_terms(
                        date_ref=invoice.date_order or  fields.Date.today(),
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
                        'date_maturity': fields.Date.to_date(invoice.invoice_date_due),
                        'discount_date': False,
                        'discount_percentage': 0
                    })] = {
                        'balance': invoice.price_total,
                        'amount_currency': invoice.price_total,
                    }
    # onchange methods
    @api.onchange('currency_id')
    def _onchange_currency_order(self):
        for order in self:
            if order.currency_id:
                """Itero sobre todas las líneas"""
                for cashLine in order.cash_lines:
                    cashLine.currency_id=order.currency_id
                for creditLine in order.credit_lines:
                    creditLine.currency_id=order.currency_id
                for productLine in order.product_lines:
                    productLine.currency_id=order.currency_id
            else:
                """Itero sobre todas las líneas"""
                for cashLine in order.cash_lines:
                    cashLine.currency_id=False
                for creditLine in order.credit_lines:
                    creditLine.currency_id=False
                for productLine in order.product_lines:
                    productLine.currency_id=False

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            args = args or []
            domain = [('active','=',True)]
            return self.search(expression.AND([domain, args]), limit=limit).name_get()
        
    def name_get(self):
        result = []
        for ast in self:
            name = '%s - (%s) - F° %s' % (ast.name, ast.short_name, ast.date_order)
            result.append((ast.id, name))
        return result
    
    # Basics
    short_name = fields.Char(string='Reference', default='New',
                         required=True, copy=False, readonly=True)
    name = fields.Char(string='Name', required=True, tracking=True)
    origin = fields.Char(string='Source Document')
    description=fields.Text(string='Description', help='Add a description to the document')
    date_order = fields.Date(string='Subscription Date')
    date_approve = fields.Datetime('Confirmation Date', readonly=1, index=True, copy=False)
    priority = fields.Selection(selection=[('0', 'Normal'), ('1', 'Urgent')], string='Priority', default='0', index=True)
    date_due = fields.Date(
        string='Integration Date', 
        help="This field is used for payable and receivable journal entries. "
             "You can put the limit date for the payment of this line.", compute='_compute_invoice_date_due')   
    date_planned = fields.Datetime(
        string='Expected Arrival', index=True, copy=False, compute='_compute_date_planned', store=True, readonly=False,
        help="Delivery date promised by vendor. This date is used to determine expected arrival of products.")
    active=fields.Boolean(string='Archived', default=False, help='field that files the document')
    notes=fields.Html(string='Notes')
    needed_terms = fields.Binary(compute='_compute_needed_terms')
    # Shares
    share_qty = fields.Integer(
        string='Quantity Shares', required='True')
    nominal_value = fields.Float(related='company_id.share_price',
                                 string='Issue Value', required=True, copy=True)
    price = fields.Monetary(string='Agreed value in the subscription',
                        help='The value at which the share was sold, the total amount that the shareholder paid to acquire the share', readonly=True, copy=False, store=True, currency_field='company_currency_id',
                        compute='_compute_share_price')
    
    price_total = fields.Monetary(
        string='Nominal Total', store=True, currency_field='company_currency_id',
        readonly=True, 
        compute='_compute_amount_total', help='Total amount of share price')

    # Relational fields

    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company.id)

    partner_id = fields.Many2one(
        string='Shareholder', comodel_name='res.partner')
    payment_term_id = fields.Many2one(comodel_name='account.payment.term', string='Pay Terms',required=True)

    # === Currency fields === #
    company_currency_id = fields.Many2one(
        string='Company Currency',
        related='company_id.currency_id', readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        tracking=True, help='If you choose one currency for the entire order, the import currency for each line will be set to that currency, leave this field empty to set a different currency for each line.',
        required=False,
        store=True, readonly=False,
    )
    # asiento de subscripcion correspondiente
    account_move_count=fields.Integer(compute="_compute_move", string='Move Count', copy=False, default=0, store=True)
    account_move = fields.Many2many(string='Accounting entry', compute="_compute_move", comodel_name='account.move', index=True, help='Related accounting entry', readonly=True, domain=[('move_type', '=', 'suscription')])
    user_id = fields.Many2one('res.users', string='User',
                              index=True, tracking=True, default=lambda self: self.env.user)
    stage_id=fields.Many2one(string='State', comodel_name='account.suscription.order.stage', default=_default_order_stage)
    state=fields.Selection(string='State',related='stage_id.order_state',readonly=True, selection=[
        ('draft','Draft'), # se permite modificaciones
        ('new','New'), # se cierran las modificaciones
        ('approved','Approved'), # se vuelven a permitir algunas modficaciones, relacionadas a las lineas, para hacer coincidir con price_total
        ('subscribed','Subscribed'), # se bloquea la edicion de nuevo
        ('finished','Finished'), # se bloquea la edicion totalmente
        ('canceled','Canceled'), # se bloquea la edicion totalmente, pero se permite volver a borrador
        ])
    # Amount Fields
    qty_pending = fields.Monetary(string='Amount pending integration', currency_field='company_currency_id',
                                  help='Amount that has not been integrated')
    qty_progress=fields.Integer(string='Porcentage', default=0)

    mail_reminder_confirmed = fields.Boolean("Reminder Confirmed", default=False, readonly=True, copy=False, help="True if the reminder email is confirmed by the vendor.")
    mail_reception_confirmed = fields.Boolean("Reception Confirmed", default=False, readonly=True, copy=False, help="True if PO reception is confirmed by the vendor.")

    receipt_reminder_email = fields.Boolean('Receipt Reminder Email', related='partner_id.receipt_reminder_email', readonly=False)
    reminder_date_before_receipt = fields.Integer('Days Before Receipt', related='partner_id.reminder_date_before_receipt', readonly=False)

    @api.depends('order_line.invoice_lines.move_id')
    def _compute_invoice(self):
        for order in self:
            invoices = order.mapped('order_line_ids.move_lines.move_id')
            order.account_move = invoices
            order.account_move_count = len(invoices)
    @api.constrains('date_due')
    def _check_date_due(self):
        for order in self:
            if order.date_due> (order.date_due+relativedelta(years=2)):
                raise ValidationError(_("The deadline for integration cannot be more than 2 years"))
    # ACTIONS METHODS
    def confirm_reminder_mail(self, confirmed_date=False):
        for order in self:
            if order.stage_id.state in ['approved', 'suscribed'] and not order.mail_reminder_confirmed:
                order.mail_reminder_confirmed = True
                date = confirmed_date or self.date_planned.date()
                order.message_post(body=_("%s confirmed the receipt will take place on %s.", order.partner_id.name, date))
    
    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        if self.env.context.get('mark_rfq_as_sent'):
            self.filtered(lambda o: o.state == 'draft').write({'state': 'sent'})
        return super(SuscriptionOrder, self.with_context(mail_post_autofollow=self.env.context.get('mail_post_autofollow', True))).message_post(**kwargs)
    
    def action_create_suscription(self):
        """Create the suscription associated to the SO.
        """
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')

        # 1) Prepare suscription vals and clean-up the section lines
        suscription_vals_list = []
        sequence = 10
        for order in self:
            if order.state != 'approved':
                continue

            order = order.with_company(order.company_id)
            pending_section = None
            # Invoice values.
            suscription_vals = order._prepare_suscription()
            # Invoice line values (asset ad product) (keep only necessary sections).

            debit_line = {
                'display_type': 'line_note',
                'account_id': (self.partner_id.property_account_subscription_id.id) or (self.env['ir.config_parameter'].get_param(
                'higher_authority.property_account_subscription_id').id),
                'debit': self.qty_to_subscribe or 0,
                'suscription_order_id': self.id
            }
            discount_line = {
                'display_type': 'line_note',
                'account_id': (self.partner_id.property_account_issue_discount_id.id) or (self.env['ir.config_parameter'].get_param(
                'higher_authority.property_account_issue_discount_id').id),
                'debit': (self.share_issuance.issue_discount)*(self.share_issuance.shares_qty) or 0,
                'suscription_order_id': self.id
            }
            premium_line = {
                'display_type': 'line_note',
                'account_id': (self.partner_id.property_account_issue_premium_id.id) or (self.env['ir.config_parameter'].get_param(
                'higher_authority.property_account_issue_discount_id').id),
                'credit': (self.share_issuance.issue_premium)*(self.share_issuance.shares_qty) or 0,
                'suscription_order_id': self.id
            }
            capital_line = {
                'display_type': 'line_note',
                'account_id': (self.partner_id.property_account_shareholding_id.id) or (self.env['ir.config_parameter'].get_param(
                'higher_authority.property_account_shareholding_id').id),
                'credit': (self.share_issuance.nominal_value)*(self.share_issuance.shares_qty) or 0,
                'suscription_order_id': self.id
            }

            suscription_vals['line_ids'].append((0, 0, debit_line))
            suscription_vals['line_ids'].append((0, 0, discount_line))
            suscription_vals['line_ids'].append((0, 0, premium_line))
            suscription_vals['line_ids'].append((0, 0, capital_line))

            suscription_vals_list.append(suscription_vals)

        # 3) Create invoices.
        SusMoves = self.env['account.move']
        AccountMove = self.env['account.move'].with_context(
            default_move_type='suscription')
        for vals in suscription_vals_list:
            SusMoves |= AccountMove.with_company(
                vals['company_id']).create(vals)

        # 4) Some moves might actually be refunds: convert them if the total amount is negative
        # We do this after the moves have been created since we need taxes, etc. to know if the total
        # is actually negative or not
        SusMoves.filtered(lambda m: m.currency_id.round(m.amount_total)
                          < 0).action_switch_invoice_into_refund_credit_note()

        return self.action_view_suscription(SusMoves)

    def _prepare_suscription(self):
        """Prepare the dict of values to create the new invoice for a purchase order.
        """
        self.ensure_one()
        move_type = self._context.get('default_move_type', 'suscription')

        partner_invoice = self.env['res.partner'].browse(
            self.partner_id.partner_id.address_get(['invoice'])['invoice'])
        partner_bank_id = self.partner_id.partner_id.commercial_partner_id.bank_ids.filtered_domain(
            ['|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)])[:1]

        suscription_vals = {
            'ref': self.partner_ref or '',
            'move_type': move_type,
            'narration': self.notes,
            'currency_id': self.currency_id.id,
            'invoice_user_id': self.user_id and self.user_id.id or self.env.user.id,
            'partner_id': self.partner_id.id,
            'fiscal_position_id': (self.fiscal_position_id or self.fiscal_position_id._get_fiscal_position(partner_invoice)).id,
            'payment_reference': self.partner_ref or '',
            'partner_bank_id': partner_bank_id.id,
            'invoice_origin': self.name,
            'invoice_payment_term_id': self.payment_term_id.id,
            'suscription_id': self.id,
            'line_ids': [],
            'company_id': self.company_id.id,
        }
        return suscription_vals

    def action_view_integration(self, integrations=False):
        """This function returns an action that display existing  integrations entries of
        given Integration order ids. When only one found, show the integration entries
        immediately.
        """
        if not integrations:
            # Invoice_ids may be filtered depending on the user. To ensure we get all
            # suscriptions related to the suscription order, we read them in sudo to fill the
            # cache.
            self.invalidate_model(['integration_order'])
            self.sudo()._read(['integration_order'])
            integrations = self.integration_orders

        result = self.env['ir.actions.act_window']._for_xml_id(
            'higher_authority.action_move_in_integration_type')
        # choose the view_mode accordingly
        if len(integrations) > 1:
            result['domain'] = [('id', 'in', integrations.ids)]
        elif len(integrations) == 1:
            res = self.env.ref('higher_authority.view_integration_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in result:
                result['views'] = form_view + \
                    [(state, view)
                     for state, view in result['views'] if view != 'form']
            else:
                result['views'] = form_view
            result['res_id'] = integrations.id
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result

    def action_view_suscription(self, suscriptions=False):
        """This function returns an action that display existing  suscriptions entries of
        given suscription order ids. When only one found, show the suscriptions entries
        immediately.
        """
        if not suscriptions:
            # Invoice_ids may be filtered depending on the user. To ensure we get all
            # suscriptions related to the suscription order, we read them in sudo to fill the00
            # cache.
            self.invalidate_model(['account_move'])
            self.sudo()._read(['account_move'])
            suscriptions = self.account_move

        result = self.env['ir.actions.act_window']._for_xml_id(
            'higher_authority.action_move_suscription_type')
        # choose the view_mode accordingly
        if len(suscriptions) > 1:
            result['domain'] = [('id', 'in', suscriptions.ids)]
        elif len(suscriptions) == 1:
            res = self.env.ref('higher_authority.view_suscription_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in result:
                result['views'] = form_view + \
                    [(state, view)
                     for state, view in result['views'] if view != 'form']
            else:
                result['views'] = form_view
            result['res_id'] = suscriptions.id
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result

    def button_approve(self):
        for order in self:
            if order.state == 'new':
                order.state == 'aproved'
                order._action_create_share_issuance()
            else:
                raise UserError('La accion ya fue aprobada o cancelada')

    def button_confirm(self):
        for order in self:
            if order.state == 'aproved':
                int_vals = order._create_integration_order()
                self.env['integration.order'].create(int_vals)
            else:
                raise UserError('No se puede confirmar esta orden')
    # metodos

    def _compute_total_cash(self):
        total = 0
        for order in self:
            for cash_line in order.cash_lines:
                total += cash_line.amount
        return total

    def _action_create_share_issuance(self):
        self.ensure_one()
        """Crea la emision de acciones correspondiente para 
            ser tratada por la asamblea
        """
        vals = {
            'suscription_order': self.id,
            'short_name': self.number,
            'makeup_date': fields.Datetime.now(),
            'nominal_value': self.nominal_value,
            'price': self.price,
            'issue_premium': self.issue_premium,
            'issue_discount': self.issue_discount,
            'company_id': self.company_id,
            'partner_id': self.partner_id.id,
        }
        self.env['shares.issuance'].create(vals)
        return True

    def action_create_integration(self):
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')

        # 1) Prepare integration vals

        integration_vals_list = []

        for order in self:
            if order.state != 'approved':
                continue

            order = order.with_company(self.company_id)
            # integration_vals
            integration_vals = self._prepare_integration_order()
            # lines
            # primero las lineas de crédito
            for credit_line in order.credit_lines:
                if not float_is_zero(credit_line.amount, precision_digits=precision):
                    continue
                line_credit_vals = credit_line._prepare_credit_line_vals()
                integration_vals['credit_lines'].append(
                    (0, 0, line_credit_vals))
            # luego las lineas de productos y activos fijos y/o intagibles

            for line in order.product_lines:
                if not float_is_zero(line.price_total, precision_digits=precision):
                    continue
                line_vals = line._prepare_order_line()
                integration_vals['product_lines'].append((0, 0, line_vals))
        integration_vals_list.append(integration_vals)

        # 3) Create invoices.
        intOrder = IntegrationOrder = self.env['integration.order']

        for vals in integration_vals_list:
            intOrder |= IntegrationOrder.with_company(
                vals['company_id']).create(vals)

        return self.action_view_integration(integrations=intOrder)

    def _prepare_integration_order(self):
        self.ensure_one()
        res = {
            'nominal_value': self.nominal_value,
            'price': self.price,
            'issue_premium': self.issue_premium,
            'issue_discount': self.issue_discount,
            'cash_subscription': self._compute_total_cash(),
            'subscription_order': self.id,
            'partner_id': self.partner_id.id,
            'origin': self.number,
            'date_order': fields.Datetime.now(),
            'partner_id': self.partner_id.partner_id,
            'state': 'draft',
            'order_line': [],
            'date_planned': self.integration_date_due,
            'payment_term_id': self.payment_term_id,
            'share_issuance': self.share_issuance,
            'credit_lines': []
        }
        return res

    # low level methods

    @api.model
    def create(self, vals):
        if vals.get('short_name', _('New')) == _('New'):
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'account.suscription.order') or _('New')
        return super().create(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_cancelled(self):
        for order in self:
            if not order.state == 'cancel':
                raise UserError(
                    _('In order to delete a suscription order, you must cancel it first.'))
    # restricciones

    @api.constrains('amount_total')
    def _check_amount_total(self):
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')
        for order in self:
            diference = abs(order.qty_to_subscribe-order.amount_total)
            dif_per = 0 if float_is_zero(diference, precision_digits=precision) else \
                (diference/order.amount_total)
            if dif_per > 0.2:
                raise ValidationError(
                    'La diferencia entre la cantidad prometida y la cantidad integrada, no puede ser superior al 20%. \n Revea la emision de acciones correspondiente')
