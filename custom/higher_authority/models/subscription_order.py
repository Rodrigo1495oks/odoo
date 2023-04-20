# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import collections
from functools import lru_cache
import hashlib
from itertools import groupby
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

from odoo import models, fields, api, tools, _

from odoo.osv.expression import get_unaccent_wrapper

from odoo.exceptions import ValidationError

from odoo.addons.base.models.res_partner import _tz_get
from odoo.addons.calendar.models.calendar_attendee import Attendee
from odoo.addons.calendar.models.calendar_recurrence import weekday_to_field, RRULE_TYPE_SELECTION, END_TYPE_SELECTION, MONTH_BY_SELECTION, WEEKDAY_SELECTION, BYDAY_SELECTION
from odoo.tools.translate import _
from odoo.tools.misc import get_lang
from odoo.tools import pycompat
from odoo.exceptions import UserError, AccessError


class SuscriptionOrder(models.Model):
    _name = 'suscription.order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Objeto Subscripción de Acciones'
    _order = 'number desc, name desc'
    _rec_name = 'number'

    # metodos computados
    @api.depends('product_id', 'cash_id')
    def _compute_qty_to_subscribe(self):
        for order in self:
            for line in order.suscription_lines:
                order.qty_to_subscribe += line.amount_currency \
                    if line.amount_currency and line.amount_currency > 0 else line.price_total

    @api.depends('shares')
    def _compute_amount_total(self):
        for order in self:
            for share in order.shares:
                amount_total += share.price

    @api.depends('integration_order')
    def _compute_qty_integrated(self):
        for order in self:
            for integration in order.integration_orders:
                order.qty_integrated += integration.amount_total_order
                if order.qty_integrated == integration.qty_to_integrate:
                    order.pending = False
                else:
                    order.pending = True

    @api.depends('qty_integrated')
    def _compute_qty_pending(self):
        for order in self:
            order.qty_pending = order.qty_integrated-order.amount_total

    number = fields.Char(string='Referencia', default='New',
                         required=True, copy=False)
    name = fields.Char(string='Nombre', required=True, tracking=True)
    suscription_date = fields.Date(string='Fecha de Subscripción')
    integration_date_due = fields.Date(
        string='Fecha de integración', help='Coloque aquí la fecha estimada de integración', states={'draft': [('readonly', False)]})
    # code = fields.Integer(string='Código', required=True)
    payment_term_id = fields.Many2one('account.payment.term', 'Payment Terms',
                                      domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('approved', 'Aprobado'),
        ('confirm', 'Confirmado'),
        ('cancel', 'Cancelado')
    ], default='draft')

    origin = fields.Char(string='Documento Origen')
    pending = fields.Boolean(string='Pendiente', default=True)
    share_qty = fields.Integer(
        string='Cantidad de acciones a subscribir', required='True')
    nominal_value = fields.Float(related='share_issuance.nominal_value',
                                 string='Valor de Emisión', required=True, copy=True)
    price = fields.Float(related='share_issuance.price', string='Valor pactado en la suscripción',
                         help='El el valor al cual se vendió la accion, el monto total que pago el accionista por adquirir la acción', readonly=True, copy=True, readonly=True, store=True)

    issue_premium = fields.Float(related='share_issuance.issue_premium',
                                 string='Prima de emision', help='Cotizacion sobre la par', readonly=True, store=True)

    issue_discount = fields.Float(related='share_issuance.issue_discount',
                                  string='Descuento de Emisión', help='Descuento bajo la par', readonly=True, store=True)

    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company.id)

    # === Currency fields === #
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
        states={'posted': [('readonly', True)], 'cancel': [
            ('readonly', True)]},
    )
    qty_to_subscribe = fields.Monetary(
        string='Cantidad a Subscribir', currency_field='company_currency_id', compute='_compute_qty_to_subscribe')

    amount_total = fields.Monetary(
        string='Total', store=True, readonly=True, compute='_compute_amount_total')

    qty_integrated = fields.Monetary(string='Cantidad Integrada', currency_field='company_currency_id',
                                     compute='_compute_qty_integrated', help='Cantidad que se ha integrado')

    qty_pending = fields.Monetary(string='Cantidad pendiente de integrar', currency_field='company_currency_id',
                                  compute='_compute_qty_pending', help='Cantidad que no se ha subscripto')

    # campos relacionales
    credit_lines = fields.One2many(string='Líneas de Crédito', comodel_name='suscription.order.line.credit', inverse_name='order_id', copy=False, readonly=True,

                                   states={'draft': [('readonly', False)]})
    cash_lines = fields.One2many(string='Líneas de Efectivo', comodel_name='suscription.order.line.cash', inverse_name='order_id', copy=False, readonly=True,
                                 states={'draft': [('readonly', False)]})

    product_lines = fields.One2many(string='Líneas de Activos', comodel_name='suscription.order.line', inverse_name='order_id', copy=False, readonly=True,
                                    states={'draft': [('readonly', False)]}, help='Sólo Productos Físicos no servicios')

    shareholder_id = fields.Many2one(
        string='Accionista', comodel_name='account.shareholder')

    # shares = fields.One2many(string='Acciones a emitir', help='Acciones creadas',
    #                          comodel_name='account.share', inverse_name='suscription_order', index=True)
    share_issuance = fields.One2many(
        string='Orden de Emisión', readonly=True, index=True, store=True, comodel_name='shares.issuance', inverse_name='suscription_order')

    topic = fields.Many2one(string='Tema de Reunión',
                            comodel_name='assembly.meeting.topic', ondelete='restrict')

    integration_orders = fields.One2many(string='Orden de Integración', comodel_name='integration.order', inverse_name='suscription_order',
                                         help='Campo técnico usado para relacionar la orden de suscripcion ocn la de integracion respectiva')

    # asiento de subscripcion correspondiente
    account_move = fields.Many2one(string='Asiento contable', comodel_name='account.move', index=True,
                                   help='Asiento contable Relacionado', readonly=True, domain=[('move_type', '=', 'suscription')])
    user_id = fields.Many2one('res.users', string='Empleado',
                              index=True, tracking=True, default=lambda self: self.env.user)
    # ACTIONS METHODS

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
                'suscription_line_id': self.id,
                'account_id': self.shareholder_id.property_account_shareholding_id.id,
                'debit': self.qty_to_subscribe,
            }
            credit_line = {
                'display_type': 'line_note',
                'suscription_line_id': self.id,
                'account_id': self.shareholder_id.property_account_suscription_id.id,
                'credit': self.qty_to_subscribe,
            }
            suscription_vals['line_ids'].append(
                (0, 0, debit_line))
            suscription_vals['line_ids'].append(
                (0, 0, credit_line))

            suscription_vals_list.append(suscription_vals)

        # 3) Create invoices.
        IntMoves = self.env['suscription.move']
        SuscriptionMove = self.env['suscription.move'].with_context(
            default_move_type='suscription')
        for vals in suscription_vals_list:
            IntMoves |= SuscriptionMove.with_company(
                vals['company_id']).create(vals)

        # 4) Some moves might actually be refunds: convert them if the total amount is negative
        # We do this after the moves have been created since we need taxes, etc. to know if the total
        # is actually negative or not
        IntMoves.filtered(lambda m: m.currency_id.round(m.amount_total)
                          < 0).action_switch_invoice_into_refund_credit_note()

        return self.action_view_suscription(IntMoves)

    def _prepare_suscription(self):
        """Prepare the dict of values to create the new invoice for a purchase order.
        """
        self.ensure_one()
        move_type = self._context.get('default_move_type', 'suscription')

        partner_invoice = self.env['res.partner'].browse(
            self.shareholder_id.partner_id.address_get(['invoice'])['invoice'])
        partner_bank_id = self.shareholder_id.partner_id.commercial_partner_id.bank_ids.filtered_domain(
            ['|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)])[:1]

        suscription_vals = {
            'ref': self.partner_ref or '', 
            'move_type': move_type,
            'narration': self.notes,
            'currency_id': self.currency_id.id,
            'invoice_user_id': self.user_id and self.user_id.id or self.env.user.id,
            'shareholder_id': self.shareholder_id.id,
            'fiscal_position_id': (self.fiscal_position_id or self.fiscal_position_id._get_fiscal_position(partner_invoice)).id,
            'payment_reference': self.partner_ref or '',  
            'partner_bank_id': partner_bank_id.id,
            'invoice_origin': self.name,
            'invoice_payment_term_id': self.payment_term_id.id,
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
            'higher_authority.action_move_integration_type')
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
            'shareholder': self.shareholder_id.id,
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
            'shareholder_id': self.shareholder_id.id,
            'origin': self.number,
            'date_order': fields.Datetime.now(),
            'partner_id': self.shareholder_id.partner_id,
            'state': 'draft',
            'order_line': [],
            'date_planned': self.integration_date_due,
            'payment_term_id': self.payment_term_id,
            'credit_lines': []
        }
        return res
    
     # low level methods
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['reference'] = self.env['ir.sequence'].next_by_code(
                'suscription.order') or 'New'
        res = super(SuscriptionOrder, self.create(vals))
        return res
    
    @api.ondelete(at_uninstall=False)
    def _unlink_if_cancelled(self):
        for order in self:
            if not order.state == 'cancel':
                raise UserError(_('In order to delete a purchase order, you must cancel it first.'))
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


class suscriptionOrderLine(models.Model):
    _name = 'suscription.order.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # _inherits = {'calendar.event': 'event_id'}
    _description = 'Objeto Línea Subscripción de Acciones'
    _order = 'short_name desc, move_name desc'
    _rec_name = 'short_name'

    order_id = fields.Many2one(string='Orden', comodel_name='suscription.order', index=True, required=True, readonly=True, auto_join=True, ondelete="cascade",
                               check_company=True,
                               help="La orden de esta linea.")

    @api.depends('quantity', 'discount', 'price_unit', 'tax_ids', 'currency_id')
    def _compute_totals(self):
        for line in self:
            if line.type != 'product':
                line.price_total = line.price_subtotal = False
            # Compute 'price_subtotal'.
            line_discount_price_unit = line.price_unit * \
                (1 - (line.discount / 100.0))
            subtotal = line.quantity * line_discount_price_unit

            # Compute 'price_total'.
            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    line_discount_price_unit,
                    quantity=line.quantity,
                    currency=line.currency_id,
                    product=line.product_id,
                    partner=line.partner_id,
                    is_refund=line.is_refund,
                )
                line.price_subtotal = taxes_res['total_excluded']
                line.price_total = taxes_res['total_included']
            else:
                line.price_total = line.price_subtotal = subtotal

    def _compute_partner_id(self):
        for line in self:
            line.partner_id = line.shareholder_id.line.partner_id.commercial_partner_id

    @api.depends('type')
    def _compute_quantity(self):
        for line in self:
            line.quantity = 1 if line.type == 'product' else False

    @api.depends('product_id', 'product_uom_id')
    def _compute_price_unit(self):
        for line in self:
            if not line.product_id:
                continue
            document_type = 'suscription'
            line.price_unit = line.product_id._get_tax_included_unit_price(
                line.move_id.company_id,
                line.move_id.currency_id,
                line.move_id.date,
                document_type,
                fiscal_position=line.move_id.fiscal_position_id,
                product_uom=line.product_uom_id,
            )
    # action methods

    short_name = fields.Char(string='Referencia')

    company_id = fields.Many2one(
        related='order_id.company_id', store=True, readonly=True, precompute=True,
        index=True,
    )
    company_currency_id = fields.Many2one(
        string='Company Currency',
        related='order_id.company_currency_id', readonly=True, store=True, precompute=True,
    )
    move_name = fields.Char(
        string='Number',
        related='order_id.name', store=True,
        index='btree',
    )
    parent_state = fields.Selection(related='order_id.state', store=True)
    date = fields.Date(
        related='order_id.date', store=True,
        copy=False,
        group_operator='min',
    )
    ref = fields.Char(
        related='order_id.short_name', store=True,
        copy=False,
        index='trigram',
    )

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner',
        compute='_compute_partner_id', store=True, readonly=False, precompute=True,
        ondelete='restrict',
    )
    shareholder_id = fields.Many2one(
        string='Accionista', comodel_name='account.shareholder')

    # ==============================================================================================
    #                                          FOR account_move_line
    # ==============================================================================================

    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        inverse='_inverse_product_id',
        ondelete='restrict',
    )
    product_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='Unit of Measure',
        store=True, readonly=False, precompute=True,
        domain="[('category_id', '=', product_uom_category_id)]",
        ondelete="restrict",
    )
    product_uom_category_id = fields.Many2one(
        comodel_name='uom.category',
        related='product_id.uom_id.category_id',
    )
    quantity = fields.Float(
        string='Quantity',
        compute='_compute_quantity', store=True, readonly=False, precompute=True,
        digits='Product Unit of Measure',
        help="The optional quantity expressed by this line, eg: number of product sold. "
             "The quantity is not a legal requirement but is very useful for some reports.",
    )

    # === Price fields === #
    price_unit = fields.Float(
        string='Unit Price',
        compute="_compute_price_unit", store=True, readonly=False, precompute=True,
        digits='Product Price',
    )
    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_totals', store=True,
        currency_field='currency_id',
    )
    price_total = fields.Monetary(
        string='Total',
        compute='_compute_totals', store=True,
        currency_field='currency_id',
    )
    discount = fields.Float(
        string='Discount (%)',
        digits='Discount',
        default=0.0,
    )

    # campos para arrastrar los activos Fijos

    asset_profile_id = fields.Many2one(
        comodel_name="account.asset.profile",
        string="Asset Profile",
        store=True,
        readonly=False,
    )
    asset_id = fields.Many2one(
        comodel_name="account.asset",
        string="Asset",
        ondelete="restrict",
    )

    def _prepare_order_line(self):
        self.ensure_one()

        vals = {
            'short_name': self.short_name,
            'company_id': self.company_id.id,
            'company_currency_id': self.company_currency_id.id,
            'move_name': self.move_name,
            'parent_state': self.parent_state,
            'date': fields.Datetime.now(),
            'ref': self.ref,
            'partner_id': self.partner_id,
            'shareholder_id': self.shareholder_id.id,
            'suscription_order_line': self.id,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_uom_id.id,
            'product_uom_category_id': self.product_uom_category_id.id,
            'quantity': self.quantity,
            'price_unit': self.price_unit,
            'price_subtotal': self.price_subtotal,
            'price_total': self.price_total,
            'discount': self.discount,
            'asset_profile_id': self.asset_profile_id.id
        }
        return vals


class suscriptionOrderLineCredit(models.Model):
    _name = 'suscription.order.line.credit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # _inherits = {'calendar.event': 'event_id'}
    _description = 'Objeto Línea Subscripción de Acciones - credito'
    _order = 'source_document desc, amount desc'
    _rec_name = 'source_document'

    order_id = fields.Many2one(string='Orden', comodel_name='suscription.order', index=True, required=True, readonly=True, auto_join=True, ondelete="cascade",
                               check_company=True,
                               help="La orden de esta linea.")

    @api.depends('currency_id', 'company_id', 'move_id.date')
    def _compute_currency_rate(self):
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
                date=line.move_id.invoice_date or line.move_id.date or fields.Date.context_today(
                    line),
            )

    @api.depends('currency_rate', 'amount')
    def _compute_amount_currency(self):
        for line in self:
            if line.amount_currency is False:
                line.amount_currency = line.currency_id.round(
                    line.amount * line.currency_rate)
            if line.currency_id == line.company_id.currency_id:
                line.amount_currency = line.amount

    @api.depends('order_id.currency_id')
    def _compute_currency_id(self):
        for line in self:
            line.currency_id = line.currency_id or line.company_id.currency_id

    @api.depends('currency_id', 'company_currency_id')
    def _compute_same_currency(self):
        for record in self:
            record.is_same_currency = record.currency_id == record.company_currency_id

    @api.onchange('amount_currency', 'currency_id')
    def _inverse_amount_currency(self):
        for line in self:
            if line.currency_id == line.company_id.currency_id and line.value != line.amount_currency:
                line.value = line.amount_currency
            elif (
                line.currency_id != line.company_id.currency_id
                and not line.order_id.is_invoice(True)
                and not self.env.is_protected(self._fields['value'], line)
            ):
                line.value = line.company_id.currency_id.round(
                    line.amount_currency / line.currency_rate)
        # Do not depend on `move_id.partner_id`, the inverse is taking care of that

    # methods

    def _prepare_credit_line_vals(self):
        self.ensure_one()
        vals = {
            'amount': self.amount,
            'partner_id': self.partner_id,
            'source_document': self.source_document,
            'amount_currency': self.amount_currency,
            'company_currency_id': self.company_currency_id.id,
            'currency_id': self.currency_id.id,
            'is_same_currency': self.is_same_currency,
            'suscription_line_id': self.id
        }
        return vals

    amount = fields.Monetary(
        string='Monto', help='Monto extraido de la ultima valuacion de la deuda', currency_field='company_currency_id')

    partner_id = fields.Many2one(
        string='Deudor', comodel_name='res.partner', help='Titular de la deuda')

    source_document = fields.Char(string='Documento de Origen')

    # === Accountable fields === #

    currency_rate = fields.Float(
        compute='_compute_currency_rate',
        help="Currency rate from company currency to document currency.",
    )
    amount_currency = fields.Monetary(
        string='Amount in Currency',
        group_operator=None,
        compute='_compute_amount_currency', inverse='_inverse_amount_currency', store=True, readonly=False, precompute=True,
        help="The amount expressed in an optional other currency if it is a multi-currency entry.")
    company_currency_id = fields.Many2one(
        string='Company Currency',
        related='order_id.company_currency_id', readonly=True, store=True, precompute=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        compute='_compute_currency_id', store=True, readonly=False, precompute=True,
        required=True,
    )
    is_same_currency = fields.Boolean(compute='_compute_same_currency')




class suscriptionOrderLineCash(models.Model):
    _name = 'suscription.order.line.cash'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # _inherits = {'calendar.event': 'event_id'}
    _description = 'Objeto Línea Subscripción de Acciones - credito'
    _order = 'source_document desc, amount desc'
    _rec_name = 'source_document'

    order_id = fields.Many2one(string='Orden', comodel_name='suscription.order', index=True, required=True, readonly=True, auto_join=True, ondelete="cascade",
                               check_company=True,
                               help="La orden de esta linea.")

    @api.depends('currency_id', 'company_id', 'move_id.date')
    def _compute_currency_rate(self):
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
                date=line.move_id.invoice_date or line.move_id.date or fields.Date.context_today(
                    line),
            )

    @api.depends('currency_rate', 'amount')
    def _compute_amount_currency(self):
        for line in self:
            if line.amount_currency is False:
                line.amount_currency = line.currency_id.round(
                    line.amount * line.currency_rate)
            if line.currency_id == line.company_id.currency_id:
                line.amount_currency = line.amount

    @api.depends('order_id.currency_id')
    def _compute_currency_id(self):
        for line in self:
            line.currency_id = line.currency_id or line.company_id.currency_id

    @api.depends('currency_id', 'company_currency_id')
    def _compute_same_currency(self):
        for record in self:
            record.is_same_currency = record.currency_id == record.company_currency_id

    @api.onchange('amount_currency', 'currency_id')
    def _inverse_amount_currency(self):
        for line in self:
            if line.currency_id == line.company_id.currency_id and line.value != line.amount_currency:
                line.value = line.amount_currency
            elif (
                line.currency_id != line.company_id.currency_id
                and not line.order_id.is_invoice(True)
                and not self.env.is_protected(self._fields['value'], line)
            ):
                line.value = line.company_id.currency_id.round(
                    line.amount_currency / line.currency_rate)
        # Do not depend on `move_id.partner_id`, the inverse is taking care of that
    amount = fields.Monetary(
        string='Monto', help='Monto extraido de la ultima valuacion de la deuda', currency_field='company_currency_id')

    partner_id = fields.Many2one(
        string='Deudor', comodel_name='res.partner', help='Titular de la deuda')

    source_document = fields.Char(string='Documento de Origen')

    # === Accountable fields === #

    currency_rate = fields.Float(
        compute='_compute_currency_rate',
        help="Currency rate from company currency to document currency.",
    )
    amount_currency = fields.Monetary(
        string='Amount in Currency',
        group_operator=None,
        compute='_compute_amount_currency', inverse='_inverse_amount_currency', store=True, readonly=False, precompute=True,
        help="The amount expressed in an optional other currency if it is a multi-currency entry.")
    company_currency_id = fields.Many2one(
        string='Company Currency',
        related='order_id.company_currency_id', readonly=True, store=True, precompute=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        compute='_compute_currency_id', store=True, readonly=False, precompute=True,
        required=True,
    )
    is_same_currency = fields.Boolean(compute='_compute_same_currency')
