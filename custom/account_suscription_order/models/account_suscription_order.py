# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import math
from functools import lru_cache
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from odoo.osv import expression
from odoo.tools.float_utils import float_is_zero, float_compare
from odoo import models, fields, api, tools, _
from odoo.osv.expression import get_unaccent_wrapper
from odoo.exceptions import ValidationError
from odoo.addons.base.models.res_partner import _tz_get
from odoo.tools.misc import frozendict, groupby
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError
from dateutil.relativedelta import relativedelta


class SuscriptionOrder(models.Model):
    _name = 'account.suscription.order'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin', ]
    _description = 'Purpose of Share Subscription'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'

    # Basics
    sequence = fields.Integer(string='N', default=1)
    short_name = fields.Char(string='Reference', default='New', required=True, copy=False, readonly=True, store=True,
                             index=True)
    name = fields.Char(string='Name', required=True, copy=False, track_visibility=True, store=True, index=True)
    origin = fields.Char(string='Source Document', track_visibility=True)
    description = fields.Text(string='Description', help='Add a description to the document')
    date_order = fields.Date(string='Subscription Date')
    date_approve = fields.Datetime('Confirmation Date', readonly=1, index=True, copy=False, track_visibility=True)
    priority = fields.Selection(selection=[('0', 'Normal'), ('1', 'Urgent')], string='Priority', default='0',
                                index=True)
    date_due = fields.Date(string='Integration Date',
                           help="This field is used for payable and receivable journal entries. ""You can put the limit date for the payment of this line.",
                           compute='_compute_invoice_date_due', precompute=True, store=True)
    date_planned = fields.Datetime(string='Expected Arrival', index=True, track_visibility=True, copy=False,
                                   compute='_compute_date_planned', store=True, readonly=False,
                                   help="Delivery date promised by vendor. This date is used to determine expected arrival of products.")
    active = fields.Boolean(string='Active', default=True, help='field that files the document')
    notes = fields.Html(string='Notes')
    needed_terms = fields.Binary(compute='_compute_needed_terms', store=True)
    # Shares
    share_qty = fields.Integer(
        string='Quantity Shares', required='True', default=1)
    nominal_value = fields.Float(related='company_id.share_price', store=True,
                                 string='Issue Value', required=False, copy=True)
    price = fields.Monetary(string='Agreed value in the subscription',
                            help='The value at which the share was sold, the total amount that the shareholder paid to acquire the share',
                            readonly=True, copy=False, store=True, currency_field='company_currency_id',
                            compute='_compute_share_price', precompute=True)

    price_total = fields.Monetary(
        string='Nominal Total', store=True, currency_field='company_currency_id',
        readonly=True,
        compute='_compute_amount_total', help='Total amount of share price', precompute=True)
    integration_status = fields.Selection([
        ('no', 'Nothing to Integrate'),
        ('to integrate', 'Waiting Receptions and Pays'),
        ('integrated', 'Fully Integrated'),
    ], string='Integration Status', compute='_get_integrated', store=True, readonly=True, copy=False, default='no')
    # Relational fields

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

    # asiento de subscripcion correspondiente
    suscription_move_count = fields.Integer(compute="_compute_suscribed", string='Move Count', copy=False, default=0,
                                            store=True)
    suscription_move = fields.Many2many(string='Suscription entry', compute="_compute_suscribed",
                                        comodel_name='account.move', index=True, help='Related accounting entry',
                                        readonly=True, domain=[('move_type', '=', 'suscription')])
    integration_move_count = fields.Integer(compute="_compute_invoice", string='Move Count', copy=False, default=0,
                                            store=True)
    integration_move = fields.Many2many(string='Integration entry', compute="_compute_invoice",
                                        comodel_name='account.move', index=True, help='Related accounting entry',
                                        readonly=True, domain=[('move_type', '=', 'integration')])

    user_id = fields.Many2one('res.users', string='User', index=True, tracking=True, default=lambda self: self.env.user)
    stage_id = fields.Many2one(string='State', comodel_name='account.suscription.order.stage',
                               default='_default_order_stage', )
    state = fields.Selection(string='State', related='stage_id.order_state', readonly=True, selection='get_states',
                             default='draft', store=True)

    # selection=[
    # ('draft','Draft'), # se permite modificaciones
    # ('new','New'), # se cierran las modificaciones
    # ('approved','Approved'), # se vuelven a permitir algunas modficaciones, relacionadas a las lineas, para hacer coincidir con price_total
    # ('suscribed','Subscribed'), # se bloquea la edicion de nuevo
    # ('finished','Finished'), # se bloquea la edicion totalmente
    # ('canceled','Canceled'), # se bloquea la edicion totalmente, pero se permite volver a borrador
    # Amount Fields
    qty_pending = fields.Monetary(string='Amount pending integration', currency_field='company_currency_id',
                                  help='Amount that has not been integrated', compute='_compute_progress')
    qty_progress = fields.Integer(string='Porcentage', default=0, compute='_compute_progress')
    mail_reminder_confirmed = fields.Boolean("Reminder Confirmed", default=False, readonly=True, copy=False,
                                             help="True if the reminder email is confirmed by the vendor.")
    mail_reception_confirmed = fields.Boolean("Reception Confirmed", default=False, readonly=True, copy=False,
                                              help="True if PO reception is confirmed by the vendor.")
    receipt_reminder_email = fields.Boolean('Receipt Reminder Email', related='partner_id.receipt_reminder_email',
                                            readonly=False)
    reminder_date_before_receipt = fields.Integer('Days Before Receipt',
                                                  related='partner_id.reminder_date_before_receipt', readonly=False)

    # metodos computados
    # campos computados
    @api.model
    def _default_order_stage(self):
        Stage = self.env['account.suscription.order.stage']
        return Stage.search([], limit=1)

    @api.depends('share_qty')
    def _compute_amount_total(self):
        for order in self:
            order.price_total = order.price * order.share_qty

    @api.depends('company_id')
    def _compute_share_price(self):
        """Look up the latest stock quote"""
        for order in self:
            # Busco la cotizacion más reciente
            recent_quote = order.env['account.stock.quote'].search([], limit=1, order='date desc')
            order.price = recent_quote.price if recent_quote else 0

    @api.depends('needed_terms')
    def _compute_invoice_date_due(self):
        today = fields.Date.context_today(self)
        for move in self:
            move.date_due = move.needed_terms and max(
                (k['date_maturity'] for k in move.needed_terms.keys() if k),
                default=False,
            ) or move.date_due or today

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

    @api.depends('state')
    def _compute_progress(self):
        for order in self:
            if order.state not in ['suscribed', 'finished']:
                order.qty_pending = 0.0
                order.qty_progress = 0.0
                continue
            cash_lines = order.env['account.suscription.cash.line'].read_group(
                domain=[('order_id', '=', order.id)],
                fields=['amount_integrated', 'order_id'],
                groupby=['order_id']
            )
            credit_lines = order.env['account.suscription.credit.line'].read_group(
                domain=[('order_id', '=', order.id)],
                fields=['amount_integrated', 'order_id'],
                groupby=['order_id']
            )
            product_lines = order.env['account.suscription.product.line'].read_group(
                domain=[('order_id', '=', order.id)],
                fields=['amount_integrated', 'order_id'],
                groupby=['order_id']
            )
            order.qty_progress = math.floor(
                (((sum([line['amount_integrated']] for line in cash_lines)) + (
                    sum([line['amount_integrated']] for line in credit_lines)) + (
                      sum([line['amount_integrated']] for line in product_lines))) / order.price_total) * 100)
            order.qty_pending = order.price_total - (sum([line['amount_integrated']] for line in cash_lines))

    # onchange methods
    @api.onchange('currency_id')
    def _onchange_currency_order(self):
        for order in self:
            if order.currency_id:
                """Itero sobre todas las líneas"""
                for cashLine in order.cash_lines:
                    cashLine.currency_id = order.currency_id
                for credit_line in order.credit_lines:
                    credit_line.currency_id = order.currency_id
                for product_line in order.product_lines:
                    product_line.currency_id = order.currency_id
            else:
                """Itero sobre todas las líneas"""
                for cashLine in order.cash_lines:
                    cashLine.currency_id = False
                for credit_line in order.credit_lines:
                    credit_line.currency_id = False
                for product_line in order.product_lines:
                    product_line.currency_id = False

    @api.depends('state', 'cash_lines.amount_to_integrate', 'credit_lines.amount_to_integrate',
                 'product_lines.amount_to_integrate', )
    def _get_integrated(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for order in self:
            if order.state not in ('suscribed', 'finished'):
                order.integration_status = 'no'
                continue
            # Cash lines
            if any(
                    [not float_is_zero(line.amount_to_integrate, precision_digits=precision)
                     for line in order.cash_lines.filtered(lambda l: not l.display_type)],
                    [not float_is_zero(line.amount_to_integrate, precision_digits=precision)
                     for line in order.credit_lines.filtered(lambda l: not l.display_type)],
                    [not float_is_zero(line.amount_to_integrate, precision_digits=precision)
                     for line in order.product_lines.filtered(lambda l: not l.display_type)]
            ):
                order.integration_status = 'to integrate'
            elif (
                    all(
                        [float_is_zero(line.amount_to_integrate, precision_digits=precision)
                         for line in order.cash_lines.filtered(lambda l: not l.display_type)],
                        [float_is_zero(line.amount_to_integrate, precision_digits=precision)
                         for line in order.credit_lines.filtered(lambda l: not l.display_type)],
                        [float_is_zero(line.amount_to_integrate, precision_digits=precision)
                         for line in order.product_lines.filtered(lambda l: not l.display_type)]
                    )
                    and order.integration_move
            ):
                self.mapped()
                mapped_int = [line.mapped('amount_integrated') for line in order.cash_lines]
                +[line.mapped('amount_integrated') for line in order.credit_lines]
                +[line.mapped('amount_integrated') for line in order.product_lines]
                qty_int = sum(mapped_int)
                if order.price_total == qty_int:
                    order.integration_status = 'integrated'
                elif order.price_total > qty_int and qty_int > 0:
                    order.integration_status = 'to integrate'
            else:
                order.integration_status = 'no'

    @api.depends('cash_lines.suscription_line_ids.move_id', 'credit_lines.suscription_line_ids.move_id',
                 'product_lines.suscription_line_ids.move_id')
    def _compute_invoice(self):
        for order in self:
            invoices = order.mapped('cash_lines.move_lines_ids.move_id') + order.mapped(
                'credit_lines.move_lines_ids.move_id') + order.mapped(
                'product_lines.move_lines_ids.move_id')
            order.integration_move = invoices
            order.integration_move_count = len(invoices)

    @api.depends('cash_lines.suscription_line_ids.move_id', 'credit_lines.suscription_line_ids.move_id',
                 'product_lines.suscription_line_ids.move_id')
    def _compute_suscribed(self):
        for order in self:
            invoices = order.mapped('cash_lines.suscription_line_ids.move_id') + order.mapped(
                'credit_lines.suscription_line_ids.move_id') + order.mapped(
                'product_lines.suscription_line_ids.move_id')
            order.suscription_move = invoices
            order.suscription_move_count = len(invoices)

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            args = args or []
            domain = [('active', '=', True)]
            return self.search(expression.AND([domain, args]), limit=limit).name_get()

    def name_get(self):
        result = []
        for ast in self:
            name = '%s - (%s) - F° %s' % (ast.name, ast.short_name, ast.date_order)
            result.append((ast.id, name))
        return result

    @api.constrains('date_due')
    def _check_date_due(self):
        for order in self:
            if order.date_due > (order.date_due + relativedelta(years=2)):
                raise ValidationError(_("The deadline for integration cannot be more than 2 years"))

    # ACTIONS METHODS

    def get_states(self):
        states = []
        raw_data = self.env['account.suscription.order.stage'].search([]).read(['order_state'])
        for kv in raw_data:
            states.append((kv['order_state'], kv['order_state'].capitalize()))
        return states if states else [('Nothing here :(', 'Nothing here :(')]

    def confirm_reminder_mail(self, confirmed_date=False):
        for order in self:
            if order.stage_id.state in ['approved', 'suscribed'] and not order.mail_reminder_confirmed:
                order.mail_reminder_confirmed = True
                date = confirmed_date or self.date_planned.date()
                order.message_post(
                    body=_("%s confirmed the receipt will take place on %s.", order.partner_id.name, date))

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
            self.payment_term_id = self.partner_id.property_supplier_payment_term_id.id
            self.currency_id = default_currency or self.partner_id.property_purchase_currency_id.id or self.env.company.currency_id.id
        return {}

    @api.onchange('partner_id')
    def onchange_partner_id_warning(self):
        # if not self.partner_id or not self.env.user.has_group('purchase.group_warning_purchase'):
        #  return

        partner = self.partner_id

        # If partner has no warning, check its company
        if partner.purchase_warn == 'no-message' and partner.parent_id:
            partner = partner.parent_id

        if partner.purchase_warn and partner.purchase_warn != 'no-message':
            # Block if partner only has warning but parent company is blocked
            if partner.purchase_warn != 'block' and partner.parent_id and partner.parent_id.purchase_warn == 'block':
                partner = partner.parent_id
            title = _("Warning for %s", partner.name)
            message = partner.purchase_warn_msg
            warning = {
                'title': title,
                'message': message
            }
            if partner.purchase_warn == 'block':
                self.update({'partner_id': False})
            return {'warning': warning}
        return {}

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        if self.env.context.get('mark_rfq_as_sent'):
            self.filtered(lambda o: o.state == 'draft').write({'state': 'sent'})
        return super(SuscriptionOrder, self.with_context(
            mail_post_autofollow=self.env.context.get('mail_post_autofollow', True))).message_post(**kwargs)

    # Actions
    # buttons


    def button_confirm(self):
        """1. Establece el estado de la orden en New
            2. Crea una linea de efectivo en caso de haber diferencia
            3 Lidia con la validacion doble
            4.Creo las ordenes de emision en estado borrador en caso que no existan
        """
        for order in self:
            if order.state not in ['draft']:
                continue
            if order.amount_total < order.price_total:
                dif = abs(order.price_total - order.amount_total)

                order.env['account.suscription.cash.line'].create({
                    "name": "Automatic extra line",
                    'order_id': order.id,
                    'state': 'draft',
                    'description': 'New Line fir fill order',
                    'money_type': 'money',
                    'company_id': lambda self: self.env.company.id,
                    'currency_id': order.currency_id.id,
                    'date_maturity': order.date_due,
                    'price_unit': dif,
                })

            if order._approval_allowed() or order.share_issue_ids.state == 'approved':
                # Deal with double validation process
                share_issues = order.env['account.share.issuance'].search(['suscription_id', '=', order.id])

                order.button_approve() if all([issue.state == 'approved' for issue in share_issues]) else {}

            else:
                order._action_create_share_issuance()
                order.write({'state': 'new'})
        return True

    def button_cancel(self):
        for order in self:
            if order.state == 'draft':
                if order.user_has_groups(
                        'account_financial_policies.account_financial_policies_stock_market_group_manager'):
                    order.write({"state": "canceled"})
                else:
                    raise AccessError(_("Operation not allowed"))
            elif order.state == 'suscribed':
                # se puede cancelar solo si hay saldos vencidos
                if order.qty_pending and order.date_due > fields.datetime.now():
                    # 1. habrá que dar de baja la suscripcion primero por el monto no aportado
                    # 2. se cancelan las acciones sumando su precio total hasta superar el monto pendiente cancelado
                    # 3. los aportes realizados, no se tocan y se integran (asiento de integración)
                    # 4. se suman las amount_to_integrate, y con ellas se crea una asiento de deuda como contrapartida
                    order.write({"state": "canceled"})
                else:
                    return {
                        "warning": {'title': 'Warning!', 'message': "no pending overdue balances"}
                    }
            elif order.state in ['finished', 'canceled', 'approved', 'new']:
                return {'warning': {'title': 'Warning!!', 'message': 'In this state, the order cannot be canceled'}}

    def button_approve(self):
        for order in self:
            if not order.state == 'new':
                continue


            if not self.env['account.share.issuance'].search_count(domain=[('suscription_id','=',order.id),('state','=','approved')])>0:
                raise UserError(_('Cannot be authorized without an issue order'))
            # 1.
            purchase_vals = {
                "name": "Emisions costs for Subscription %s" % (order.short_name),
                "origin": order.short_name,
                "date_order": fields.Datetime.now,
                "notes": "Purchase Order for Share Issue",
                "company_id": lambda self: self.env.company.id,
                "order_line": [],
            }

            order.env['purchase.order'].create(purchase_vals)
            order.write({'state': 'approved'})

    def button_draft(self):
        for order in self:
            if order.state in ['approved']:
                order.write({'state': 'draft'})
                return True
            else:
                return {'warning': {'title': 'Warning', 'message': 'In this state, the order cannot be changed'}}

    def button_suscribe(self):
        for order in self:
            if not order.state == 'approved':
                continue
            if order.amount_total < order.price_total:
                dif = abs(order.price_total - order.amount_total)

                order.env['account.suscription.cash.line'].create({
                        "name": "Automatic extra line",
                        'order_id': order.id,
                        'state': 'draft',
                        'description': 'New Line fir fill order',
                        'money_type': 'money',
                        'company_id': lambda self: self.env.company.id,
                        'currency_id': order.currency_id.id,
                        'date_maturity': order.date_due,
                        'price_unit': dif,
                    })

            share_issues = order.env['account.share.issuance'].search_read(domain=['suscription_id', '=', order.id],
                                                                           fields=['total'])
            if sum([issue['total'] for issue in share_issues]) != order.price_total:
                return {'warning': {'title': 'Warning',
                                    'message': 'The total to be issued cannot be different from the total to be suscribed'}}

            #  . Suscribo las acciones
            for issue in share_issues:
                if issue['state']=="approved":
                    issue.action_suscribe()
            # 1. Creo el asiento de suscripción

            order._action_create_subscription()
            order.write({'state': 'suscribed'})
        return {}
    
    def button_integrate(self):
        return True
    
    def _process_line(self, sequence, lines):
        """helper to build lines for invoices
        :param sequence: we write the sequence
        :param lines: recordset
        :returns: list of lines
        """
        account_id = self.partner_id.property_account_subscription_id or self.company_id.property_account_subscription_id or \
                     self.env['account.account'].search(
                         [('type', '=', 'asset_receivable_others'), ('deprecated', '=', False),
                          ('company_id', '=', lambda self: self.env.company.id,)], limit=1)
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')
        line_ids = []
        for line in lines:
            if line.display_type == 'line_section':
                pending_section = line
                continue
            if not float_is_zero(line.price_total, precision_digits=precision):
                if pending_section:
                    line_vals = pending_section._prepare_account_move_line()
                    line_vals.update({'account_id': account_id.id, 'sequence': sequence})
                    line_ids.append((0, 0, line_vals))
                    sequence += 1
                    pending_section = None
                line_vals = line._prepare_account_move_line()
                line_vals.update({'sequence': sequence})
                line_ids.append((0, 0, line_vals))
                sequence += 1
        return line_ids

    def _action_create_subscription(self):
        """Create the suscription associated to the SO.
        """
        # 0) Prepare suscription vals and clean-up the section lines
        if not self.env['account.move'].check_access_rights('create', False):
            try:
                self.check_access_rights('write')
                self.check_access_rule('write')
            except AccessError:
                return self.env['account.move']
        # 1) Create invoices.

        suscription_vals_list = []
        sequence = 1
        for order in self:
            if order.state != 'approved':
                continue

            order = order.with_company(order.company_id)
            pending_section = None
            # Invoice values.
            suscription_vals = order._prepare_suscription()
            # Invoice line values (keep only necessary sections).


            equity_account_id = order.partner_id.property_account_integration_id or order.company_id.property_account_integration_id or \
                                order.env['account.account'].search(
                                    domain=[('account_type', '=', 'equity'), ('deprecated', '=', False),
                                            ('company_id', '=', lambda self: self.env.company.id,)], limit=1)
            cash_vals = order._process_line(sequence, order.cash_lines)
            credit_vals = order._process_line(sequence, order.credit_lines_lines)
            product_lines_vals = order._process_line(sequence, order.product_lines_lines_lines, )
            sequence += 1

            equity_line={
                "display_type":'product',
                "sequence": sequence,
                'name': "Capital Subscription Line for s% - (s%)"%(order.short_name, order.name),
                'partner_id': order.partner_id.id,
                'currency_id': order.currency_id.id,
                'quantity': 1,
                'price_unit': order.price_total,
                'price_subtotal': 1 * order.price_total,
                'amount_currency': 1 * order.price_total,
                'balance': order.currency_id._convert(
                    1 * order.price_total,
                    order.company_currency_id,
                    order.company_id, fields.Date.today(),
                ),
                'account_id': equity_account_id.id,
                # 'analytic_distribution': line.analytic_distribution,
            }
            suscription_vals['invoice_line_ids'] = product_lines_vals
            suscription_vals['line_ids'] = cash_vals + credit_vals + [equity_line]
            suscription_vals_list.append(suscription_vals)

            if not suscription_vals_list:
                raise UserError(
                    _('There is no invoiceable line. If a product has a control policy based on received quantity, please make sure that a quantity has been received.'))

        # 2) group by (company_id, partner_id, currency_id) for batch creation
        new_invoice_vals_list = []
        for grouping_keys, invoices in groupby(suscription_vals_list, key=lambda x: (
                x.get('company_id'), x.get('partner_id'), x.get('currency_id'))):
            origins = set()
            payment_refs = set()
            refs = set()
            ref_invoice_vals = None
            for invoice_vals in invoices:
                if not ref_invoice_vals:
                    ref_invoice_vals = invoice_vals
                else:
                    ref_invoice_vals['line_ids'] += invoice_vals['line_ids']
                origins.add(invoice_vals['invoice_origin'])
                payment_refs.add(invoice_vals['payment_reference'])
                refs.add(invoice_vals['ref'])
            ref_invoice_vals.update({
                'ref': ', '.join(refs)[:2000],
                'invoice_origin': ', '.join(origins),
                'payment_reference': len(payment_refs) == 1 and payment_refs.pop() or False,
            })
            new_invoice_vals_list.append(ref_invoice_vals)
        suscription_vals_list = new_invoice_vals_list

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
        SusMoves.filtered(lambda m: m.currency_id.round(m.price_total)
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
        journal_id = self.company_id.subscription_journal_id or self.env['account.journal'].search(
            ['type', '=', 'suscription'], limit=1)

        suscription_vals = {
            'ref': self.partner_ref or '',
            'move_type': move_type,
            'narration': self.notes,
            'currency_id': self.currency_id.id,
            'user_id': self.user_id and self.user_id.id or self.env.user.id,
            'partner_id': self.partner_id.id,
            'payment_reference': self.origin or '',
            'partner_bank_id': partner_bank_id.id,
            'invoice_date_due': self.date_due,
            'invoice_payment_term_id': self.payment_term_id.id,
            'invoice_origin': 'Source: (%s)  Order N° %s'%(self.name,self.short_name),
            'suscription_id': self.id,
            'line_ids': [],
            'invoice_line_ids': [],
            'company_id': self.company_id.id,
            'journal_id': journal_id.id,
        }
        return suscription_vals

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
            suscriptions = self.suscription_move
        result = self.env['ir.actions.act_window']._for_xml_id(
            'account_suscription_order.action_move_in_subscription_type')
        # choose the view_mode accordingly
        if len(suscriptions) > 1:
            result['domain'] = [('id', 'in', suscriptions.ids)]
        elif len(suscriptions) == 1:
            res = self.env.ref('account_suscription_order.view_suscription_form', False)
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

    # metodos
    def _add_supplier_to_product(self):
        # Add the partner in the supplier list of the product if the supplier is not registered for
        # this product. We limit to 10 the number of suppliers for a product to avoid the mess that
        # could be caused for some generic products ("Miscellaneous").
        for line in self.product_lines:
            # Do not add a contact as a supplier
            partner = self.partner_id if not self.partner_id.parent_id else self.partner_id.parent_id
            if line.product_id and partner not in line.product_id.seller_ids.partner_id and len(
                    line.product_id.seller_ids) <= 10:
                # Convert the price in the right currency.
                currency = partner.property_purchase_currency_id or self.env.company.currency_id
                price = self.currency_id._convert(line.price_unit, currency, line.company_id,
                                                  line.date_order or fields.Date.today(), round=False)
                # Compute the price for the template's UoM, because the supplier's UoM is related to that UoM.
                if line.product_id.product_tmpl_id.uom_po_id != line.product_uom:
                    default_uom = line.product_id.product_tmpl_id.uom_po_id
                    price = line.product_uom._compute_price(price, default_uom)

                supplierinfo = self._prepare_supplier_info(partner, line, price, currency)
                # In case the order partner is a contact address, a new supplierinfo is created on
                # the parent company. In this case, we keep the product name and code.
                seller = line.product_id._select_seller(
                    partner_id=line.partner_id,
                    quantity=line.product_qty,
                    date=line.order_id.date_order and line.order_id.date_order.date(),
                    uom_id=line.product_uom)
                if seller:
                    supplierinfo['product_name'] = seller.product_name
                    supplierinfo['product_code'] = seller.product_code
                vals = {
                    'seller_ids': [(0, 0, supplierinfo)],
                }
                # supplier info should be added regardless of the user access rights
                line.product_id.sudo().write(vals)

    def _action_create_share_issuance(self):
        self.ensure_one()
        """Crea la emision de acciones correspondiente para 
            ser tratada por la asamblea
        """
        vals = {
            "name": 'Issue for order N° %s - (%s)' % (self.short_name, self.date_order),
            'suscription_id': self.id,
            'makeup_date': fields.Datetime.now(),
            'price': self.price,
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

    def _approval_allowed(self):
        """Returns whether the order qualifies to be approved by the current user"""
        self.ensure_one()
        return (
                self.company_id.so_double_validation == 'one_step'
                or (self.company_id.so_double_validation == 'two_step'
                    and self.price_total < self.env.company.currency_id._convert(
                    self.company_id.so_double_validation_amount, self.currency_id, self.company_id,
                    self.date_order or fields.Date.today()))
                or self.user_has_groups(
            'account_financial_policies.account_financial_policies_stock_market_group_manager'))

    # low level methods

    @api.model
    def create(self, vals):
        if vals.get('short_name', _('New')) == _('New'):
            seq_date = None
            if 'date_order' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date_order']))
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'account.suscription.order', sequence_date=seq_date) or _('New')
        return super().create(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_cancelled(self):
        for order in self:

            if order.active:
                return {'warning': {'title': 'Warning!!', 'message': 'You must cancel it and archive it first'}}
            if any(not order.state in ( 'canceled' ,'suscribed','finished') or order.suscription_move_count>0 or order.integration_move_count>0):
                raise UserError(
                    _('In order to delete a suscription order, you must cancel it and archive it first. To cancel it, you must also delete all associated entries.'))


    # restricciones

    @api.constrains('price_total')
    def _check_amount_total(self):
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')
        for order in self:
            issue_ids = order.env['account.share.issuance'].search_read(domain=[('suscription_id', '=', order.id)],
                                                                        fields=['total'])
            diference = abs(sum([issue['total'] for issue in issue_ids if len(issue_ids) > 0]) - order.price_total)
            dif_per = 0 if float_is_zero(diference, precision_digits=precision) else diference
            if all([dif_per > 0.2, order.state in ('draft', 'new')]):
                message_id = self.env['message.wizard'].create(
                    {'message': _(
                        "WARNING: There are differences between the amounts promised and the shares created. Please issue the appropriate actions")})
                return {
                    'name': _('Notice!!'),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'res_model': 'message.wizard',
                    # pass the id
                    'res_id': message_id.id,
                    'target': 'new'
                }
            elif all([dif_per > 0.2, order.state == 'approved']):
                raise ValidationError(
                    _('There are differences between the amounts promised and the shares created. Please issue the appropriate actions'))

    @api.constrains('company_id', 'product_lines')
    def _check_order_line_company_id(self):
        for order in self:
            companies = order.product_lines.product_id.company_id
            if companies and companies != order.company_id:
                bad_products = order.product_lines.product_id.filtered(
                    lambda p: p.company_id and p.company_id != order.company_id)
                raise ValidationError(_(
                    "Your quotation contains products from company %(product_company)s whereas your quotation belongs to company %(quote_company)s. \n Please change the company of your quotation or remove the products from other companies (%(bad_products)s).",
                    product_company=', '.join(companies.mapped('display_name')),
                    quote_company=order.company_id.display_name,
                    bad_products=', '.join(bad_products.mapped('display_name')),
                ))