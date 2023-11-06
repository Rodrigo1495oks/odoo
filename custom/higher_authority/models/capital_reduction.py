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
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
from werkzeug import urls

from datetime import datetime, timedelta
from odoo.tools import date_utils
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


class ReductionOrder(models.Model):
    _name = 'capital.reduction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Objeto Reducción de Acciones'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'

    # metodos computados
    @api.depends('reduction_type')
    def _compute_total(self):
        for red in self:
            if red.reduction_type == 'voluntary':
                red.reduction_amount = self.manual_amount
            elif red.reduction_type == 'cancelation':
                red.reduction_amount = self._compute_total_to_cancel()

    @api.depends('reduction_ids')
    def _compute_invoice(self):
        for order in self:
            order.certificate_count = len(order.reduction_ids)
    # Campos Compútados

    @api.depends('percentage_to_reduce')
    def _compute_shares_to_cancel(self):
        for reduction in self:
            if reduction.reduction_type == 'cancelation':
                # sumo la cantidad total de acciones del accionista y recupero las que debo reducir
                shares = reduction.env['account.share'].search(
                    [('partner_id', '=', reduction.partner_id), ('state', 'in', ['suscribed', 'integrated'])], order="id desc")
                share_qty = len(shares)

                for i in range(math.floor(share_qty*reduction.percentage_to_reduce)):
                    reduction.shares |= shares[i]

    @api.depends('reduction_ids')
    def _compute_invoice(self):
        for order in self:
            reductions = order.reduction_ids
            order.invoice_count = len(order.reduction_ids)
    short_name = fields.Char(string='Referencia', default='New',
                             required=True, copy=False, readonly=True)
    name = fields.Char(string='Nombre', required=True, tracking=True)
    date = fields.Date(string='Fecha de Confección')
    date_due = fields.Date(
        string='Fecha de vencimiento', help='Coloque aquí la fecha estimada de Cancelación', states={'draft': [('readonly', False)]})
    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('approved', 'Aprobado'),
        ('confirm', 'Confirmado'),
        ('cancel', 'Cancelado')
    ], default='draft', readonly=True)
    reduction_type = fields.Selection(string='Tipo', selection=[
        ('voluntary', 'Voluntaria'),
        ('obligatory', 'Obligatoria'),
        ('cancelation', 'Cancelación de Acciones'),
    ], default='voluntary')
    # SMART BUTTON

    reduction_ids = fields.Many2many(
        'account.move', string='Reducciones', copy=False, store=True, domain=[('move_type', '=', 'reduction')])
    reduction_count = fields.Integer(
        compute="_compute_invoice", string='Reducciones', copy=False, default=0, store=True)
    shares = fields.Many2many(string='Acciones a Cancelar', help='Acciones creadas', relation='reduction_share_rel', column1='reduction', column2='share', comodel_name='account.share', inverse_name='capital_reduction',
                              index=True, domain="[('state','not in',('cancel','draft','new', 'negotiation', 'portfolio')), ('partner_id','=','partner_id')]", compute='_compute_shares_to_cancel', readonly=True)
    reduction_order = fields.Many2one(string='Órdenes de Reducción')

    manual_amount = fields.Monetary(
        string='Cantidad Manual', help='Indique la cantidad a reducir, cuando el tipo de reducción sea - voluntaria (para absorber pérdidas)')
    reduction_amount = fields.Monetary(
        string='Total', compute='_compute_total', readonly=True)

    notes = fields.Html(string='Notas')

    partner_id = fields.Many2one(
        string='Accionista', comodel_name='res.partner', required=True)

    reduction_count = fields.Integer(
        compute="_compute_invoice", string='Reducciones', copy=False, default=0, store=True)
    user_id = fields.Many2one('res.users', string='Usuario',
                              index=True, tracking=True, default=lambda self: self.env.user)
    topic = fields.Many2one(
        string='Tópico', comodel_name='assembly.meeting.topic', readonly=True)
    percentage_to_reduce = fields.Float(string='Porcentaje a Reducir', readonly=True,
                                        help='Porcentaje Proporcionado por la Orden de Cancelación', default=0.0)

    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company.id, readonly=True)
    reduction_list_id = fields.Many2one(
        string='Pedidos de Reducción', help='Solicitudes de Reducción para mantener el VPP.', comodel_name='capital.reduction.list', readonly=True)

    @api.onchange('loss_absortion')
    def _onchange_absortion(self):
        if self.loss_absortion:
            self.reduction_type = 'voluntary'
            return {'warning': {
                'title': _("Mensaje"),
                'message': ('Reducción Voluntaria')}}

    # ACTIONS

    def button_set_new(self):
        for red in self:
            if red.state == 'draft':
                red.state = 'new'

    def button_cancel(self):
        for cont in self:
            if cont.state not in ['confirm', 'cancel']:
                cont.state = 'cancel'
            else:
                raise UserError('No puede cancelarse el aporte')

    def button_approve(self):
        for red in self:
            if red.state == 'new' and red.reduction_type != 'cancelation':
                topic_vals = self._prepare_topic_values()
                self.env['assembly.meeting.topic'].create(topic_vals)
                red.state = 'approved'
            else:
                raise UserError('Acción no permitida - ')

    def button_confirm(self):
        for red in self:
            if red.state == 'approved' and red.topic.state == 'approved':
                if red.reduction_type == 'voluntary':
                    red.action_create_reduction_vol()
                elif red.reduction_type == 'obligatory':
                    red.action_create_reduction_obl()
                elif red.reduction_type == 'cancelation':
                    red.action_create_reduction_can()
                red.state = 'confirm'
            else:
                raise UserError('Acción no valida - (AC)')

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
    # lógica

    def action_create_reduction_vol(self):
        """Estaa funcion la dejo por razones de complitud \n.
            Pero no la pienso usar nunca
        """
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')

        # 1) Prepare reduction vals and clean-up the section lines
        reduction_vals_list = []
        sequence = 10
        for order in self:
            if order.state != 'approved':
                continue

            order = order.with_company(order.company_id)
            pending_section = None
            # Invoice values.
            reduction_vals = order._prepare_reduction()
            # Invoice line values (asset ad product) (keep only necessary sections).

            debit_line = {
                'display_type': 'line_note',
                'account_id': self.capital_reduction_group.counterpart_account.id,
                'debit': self.manual_amount or 0,
            }
            credit_line = {
                'display_type': 'line_note',
                'account_id': self.capital_reduction_group.profit_lost_account.id,
                'credit': self.manual_amount or 0,
            }

            reduction_vals['line_ids'].append((0, 0, debit_line))
            reduction_vals['line_ids'].append((0, 0, credit_line))

            reduction_vals_list.append(reduction_vals)

        # 3) Create invoices.
        SusMoves = self.env['account.move']
        AccountMove = self.env['account.move'].with_context(
            default_move_type='reduction')
        for vals in reduction_vals_list:
            redMove = AccountMove.with_company(
                vals['company_id']).create(vals)
            self.reduction_ids.append(0, 0, redMove)
            SusMoves |= redMove

        # 4) Some moves might actually be refunds: convert them if the total amount is negative
        # We do this after the moves have been created since we need taxes, etc. to know if the total
        # is actually negative or not
        SusMoves.filtered(lambda m: m.currency_id.round(m.amount_total)
                          < 0).action_switch_invoice_into_refund_credit_note()

        return self.action_view_reduction(SusMoves)

    def action_create_reduction_can(self):
        """Cancela acciones, y acredita el saldo al accionista.
        CREO UN ASIENTO POR CADA ORDEN Y UNA ORDEN POR CADA ACCIONISTA
        """
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')

        reduction_vals_list = []
        sequence = 10
        for order in self:

            if order.state != 'approved':
                continue
                # a- calcular el maximo importe que se podrá reducir para este accionista
            max_to_red = order._compute_max_to_red()
            # b- seleccionar las acciones a cancelar,
            # c- sumar el total a cancelar
            total_to_cancel = order._compute_total_to_cancel()
            # d- verificar si el total a cancelar no supere el maximo importe
            # EL ACCIONISTA NO PODRÁ, POR DEFECTO Y SIN ESTABLECER NINGUNA OTRA     RESTRICCIN MAS, SELECCIONAR UN MONTO MAYOR A LAS ACCIONES QUE POSEE     SUSCRIPTAS O INTEGRADAS

            if total_to_cancel > max_to_red:
                raise UserError(
                    f'El total a cancelar supera el monto máximo permitido: ${max_to_red}')
            # leer las cuentas para buscar el saldo

            property_account_shareholding_id = order.partner_id. property_account_shareholding_id.id or order.company_id.  property_account_shareholding_id or order.env['account.account'].search([
                ('internal_type', '=', 'equity')])[0]
            property_account_integration_id = order.partner_id.  property_account_integration_id.id or order.company_id.    property_account_integration_id or order.env['account.account'].search([
                ('internal_type', '=', 'equity')])[0]
            premium_issue_account = order.partner_id.    property_account_issue_premium_id.id or order.company_id.    property_account_issue_premium_id or order.env['account.account'].search([
                ('internal_type', '=', 'equity_issue_premium')])[0]
            account_capital_adjustment = order.partner_id.account_capital_adjustment or order.company_id.account_capital_adjustment or order.env['account.account'].search([
                ('internal_type', '=', 'equity_adjustment')])[0]

            property_account_issue_discount_id = order.partner_id.property_account_issue_discount_id or order.company_id. property_account_issue_discount_id or order.env['account.account'].search([
                ('internal_type', '=', 'equity_issue_discount')])[0]
            account_share_redemption_discount = order.partner_id.account_share_redemption_discount or order.company_id.   account_share_redemption_discount or order.env['account.account'].search([
                ('internal_type', '=', 'contribution')])[0]
            account_shareholders_for_redemption_of_shares = order.partner_id.    account_shareholders_for_redemption_of_shares or order.company_id.  account_shareholders_for_redemption_of_shares or order.env['account.account'].search([
                ('internal_type', '=', 'liability_payable_redemption_shares')])[0]
            # leer el saldo y determianr su valor

            # ¿Qué procentaje del capital estoy reduciendo?
            # necesito saberlo para calcular el monto de las primas de emision,     descuentos de emision y ajuste del capital a dar de baja

            # total del ajuste al capital

            total_adjustment = float(order.check_balance(
                account_capital_adjustment, fields.Date.today()))*order.percentage_to_reduce
            total_issue_premium = float(order.check_balance(
                premium_issue_account, fields.Date.today()))*order.percentage_to_reduce
            total_issue_discount = float(order.check_balance(
                property_account_issue_discount_id, fields.Date.today()))*order.percentage_to_reduce
            total_shareholders_for_redemption_of_shares = (
                total_adjustment+total_issue_premium-total_issue_discount)*(order.company_id.percentage_redemption)
            total_share_redemption_discount = float(
                total_adjustment+total_issue_premium-total_issue_discount) - total_shareholders_for_redemption_of_shares

            # yo estoy separando por capital suscripto y por capital integrado
            # encuentro los totales

            total_suscribed = order._compute_total_suscribed()
            total_integrated = order._compute_total_integrated()

            # 1) Prepare reduction vals and clean-up the section lines
            order = order.with_company(order.company_id)
            pending_section = None
            # Invoice values.
            reduction_vals = order._prepare_reduction()
            # Invoice line values (asset ad product) (keep only necessary sections).

            suscribed_line = {
                'account_id': property_account_shareholding_id,
                'debit': total_suscribed or 0,
                'reduction_order_id': self.id
            }
            integrated_line = {
                'account_id': property_account_integration_id,
                'debit': total_integrated or 0,
                'reduction_order_id': self.id
            }
            premium_line = {
                'account_id': premium_issue_account,
                'debit': total_issue_premium or 0,
                'reduction_order_id': self.id
            }
            adjustment_line = {
                'account_id': account_capital_adjustment,
                'debit': total_adjustment or 0,
                'reduction_order_id': self.id
            }
            discount_line = {
                'account_id': property_account_issue_discount_id,
                'credit': total_issue_discount or 0,
                'reduction_order_id': self.id
            }
            redemption_of_shares_line = {
                'account_id': account_shareholders_for_redemption_of_shares,
                'credit': total_shareholders_for_redemption_of_shares or 0,
                'reduction_order_id': self.id
            }
            redemption_discount_line = {
                'account_id': account_share_redemption_discount,
                'credit': total_share_redemption_discount or 0,
                'reduction_order_id': self.id
            }

            reduction_vals['line_ids'].extend((0, 0, suscribed_line), (0, 0,    integrated_line), (0, 0, suscribed_line), (0, 0, premium_line), (
                0, 0, adjustment_line), (0, 0, discount_line), (0, 0,   redemption_of_shares_line), (0, 0, redemption_discount_line))

            reduction_vals_list.append(reduction_vals)
            # e- dar de baja las acciones
            self._action_cancel_shares()
        # 3) Create invoices.
        SusMoves = self.env['account.move']
        AccountMove = self.env['account.move'].with_context(
            default_move_type='reduction')
        for vals in reduction_vals_list:
            redMove = AccountMove.with_company(
                vals['company_id']).create(vals)
            self.reduction_ids.append(0, 0, redMove)
            SusMoves |= redMove
        # 4) Some moves might actually be refunds: convert them if the total    amount is negative
        # We do this after the moves have been created since we need taxes,     etc. to know if the total
        # is actually negative or not
        SusMoves.filtered(lambda m: m.currency_id.round(m.amount_total)
                          < 0).action_switch_invoice_into_refund_credit_note()

        return self.action_view_reduction(SusMoves)

    def action_create_reduction_obl(self):
        """Create the reduction associated to the SO.
        """
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')

        # 1) Prepare reduction vals and clean-up the section lines
        reduction_vals_list = []
        sequence = 10
        for order in self:
            if order.state != 'approved':
                continue

            order = order.with_company(order.company_id)

            # Invoice values.
            reduction_vals = order._prepare_reduction()
            # Invoice line values (asset ad product) (keep only necessary sections).

            # algoritmo para calcular esto

            # 1- sumar los conceptos correspondientes (acceder al modelo de share y sumar su valor total [nominal + prima] y AI)
            # sumar también todas las reservas, determinar el monto total y ver si insume
            total_cap = self.get_capital_value()
            total_reserve = self.get_reserve_value()  # falta hacer esta
            # 2- Determinar el resultado del ejercicio (31/12 del ejercicio cerrado)
            # seleccionamos el periodo fiscal mas reciente

            # leer la cuenta para buscar el saldo
            result_account = self.company_id.financial_year_result_account or self.env['account.account'].search([
                ('internal_type', '=', 'equity_unaffected')])[0]
            # Leer las cuentas del accionista

            property_account_subscription_id = self.partner_id.property_account_subscription_id or self.company_id.property_account_subscription_id or self.env['account.account'].search([
                ('internal_type', '=', 'equity')])[0]
            property_account_integration_id = self.partner_id.property_account_integration_id or self.company_id.property_account_integration_id or self.env['account.account'].search([
                ('internal_type', '=', 'equity')])[1]

            # leer el saldo y determinar su valor
            balance = float(self.check_balance(
                result_account, self._return_last_fiscal_year().date_to or self._default_cutoff_date())) or 0
            balance = -(balance)
            # - si es pérdida: se procede al calculo
            # (sumatoria de las reservas y el 50% del capital):
            #   - comprobar si insume el 50% del capital + todas las reservas
            # - si el resultado es positivo: se lanza raise UserError('')
            if any([balance >= 0.0, not abs(balance) >= abs(total_cap/2+total_reserve)]):  # si es perdida
                return {
                    'warning': {
                        'title': 'Operación no válida',
                        'message': 'No existen pérdidas'}
                }

            # Sila condicion se cumple: prosigo:
            # itero sobre todas las reservas
            i = 0
            integrated_value = suscribed_value = 0
            order._cancel_reserve_loop(i, balance)
            order._cancel_capital_adjustment_loop(i, balance)
            order._cancel_premium_loop(i, balance)
            order._cancel_suscribed_loop(i, balance, suscribed_value)
            order._cancel_integrated_loop(i, balance, integrated_value)

            suscribed_debit = {
                'account_id': property_account_subscription_id,
                'debit': suscribed_value or 0,
                'reduction_order_id': self.id
            }
            integrated_debit = {
                'account_id': property_account_integration_id,
                'debit': integrated_value or 0,
                'reduction_order_id': self.id
            }
            credit_line = {
                'account_id': result_account,
                'credit': suscribed_value + integrated_value,
                'reduction_order_id': self.id
            }
            
            reduction_vals['line_ids'].extend(
                (0, 0, suscribed_debit), (0, 0, integrated_debit), (0, 0, credit_line))

            reduction_vals_list.append(reduction_vals)

        # 3) Create invoices.
        SusMoves = self.env['account.move']
        AccountMove = self.env['account.move'].with_context(
            default_move_type='reduction')
        for vals in reduction_vals_list:
            redMove = AccountMove.with_company(
                vals['company_id']).create(vals)
            self.reduction_ids.append(0, 0, redMove)
            SusMoves |= redMove

        # 4) Some moves might actually be refunds: convert them if the total amount is negative
        # We do this after the moves have been created since we need taxes, etc. to know if the total
        # is actually negative or not
        SusMoves.filtered(lambda m: m.currency_id.round(m.amount_total)
                          < 0).action_switch_invoice_into_refund_credit_note()

        return self.action_view_reduction(SusMoves)

    @api.multi
    def check_balance(self, account=False, date=fields.Date.today()):
        """Función que determina el saldo de la cuenta Resultados del ejercicio"""
        for red in self:
            domain = [('account_id', '=', account.id),
                      ('date', '<=', red.date)]
            move_lines = self.env['account.move.line'].search(domain)
            balance = 0
            for line in move_lines:
                balance += (line.debit - line.credit)
        return balance

    def get_capital_value(self):
        self.ensure_one()
        total_cap = 0
        # sumo  las acciones y sus primas de emision
        for share in self.env['account.share'].search([('state', 'in', '(suscribed, portfolio, negotiation)')]):
            total_cap += share.price if share.price else 0
        # sumo los aportes irrevocables cobrado
        for cont in self.env['irrevocable.contribution'].search([('state', 'in', '(approved, confirmed)')]):
            total_cap += cont.amount
        # Sumo los Ajustes de Capital por inflación
        for adj in self.env['capital.adjustment'].search([('state', 'in', '(approved, confirmed)')]):
            total_cap += adj.amount

        return total_cap

    def _compute_max_to_red(self):
        self.ensure_one()
        max_to_red = 0
        for share in self.partner_id.shares:
            max_to_red += share.nominal_value if share.state in [
                'suscribed', 'integrated'] else 0
        return max_to_red

    def _prepare_reduction(self):
        """Prepare the dict of values to create the new invoice for a purchase order.
        """
        self.ensure_one()
        move_type = self._context.get('default_move_type', 'reduction')

        partner_invoice = self.env['res.partner'].browse(
            self.partner_id.address_get(['invoice'])['invoice'])
        partner_bank_id = self.partner_id.commercial_partner_id.bank_ids.filtered_domain(
            ['|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)])[:1]

        reduction_vals = {
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
            'line_ids': [],
            'company_id': self.company_id.id,
        }
        return reduction_vals

    def action_view_reduction(self, integrations=False):
        """This function returns an action that display existing  integrations entries of
        given Integration order ids. When only one found, show the integration entries
        immediately.
        """
        if not integrations:
            # Invoice_ids may be filtered depending on the user. To ensure we get all
            # reductions related to the reduction order, we read them in sudo to fill the
            # cache.
            self.invalidate_model(['reductions_ids'])
            self.sudo()._read(['reductions_ids'])
            integrations = self.reductions_ids

        result = self.env['ir.actions.act_window']._for_xml_id(
            'higher_authority.action_move_in_reduction_type')
        # choose the view_mode accordingly
        if len(integrations) > 1:
            result['domain'] = [('id', 'in', integrations.ids)]
        elif len(integrations) == 1:
            res = self.env.ref('higher_authority.view_reduction_form', False)
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
    # api.depends('')

    def _compute_total_to_cancel(self):
        self.ensure_one()
        total_to_cancel = 0
        for share in self.shares:
            if share.state in ['suscribed', 'integrated']:
                total_to_cancel += share.nominal_value
        self.reduction_amount = total_to_cancel
        return total_to_cancel

    def _action_cancel_shares(self):
        for red in self:
            for share in red.partner_id.shares:
                share.capital_reduction = self.id
                share.share_cancel()

    def _prepare_topic_values(self):
        self.ensure_one()
        topic_values = {
            "name": "Reducción de Capital. \n",
            "description": "Reducción de Capital",
            "state": "draft",
            "topic_type": "reduction",
        }
        return topic_values

    def _return_last_fiscal_year(self):
        periods = self.env['account.fiscal.year'].browse()

        max = 0
        p = ''
        # selecciono el periodo mas reciente (ultimop ejercicio cerrado)
        for period in periods:
            if period.date_from <= self.date:
                if period.date_to >= max:
                    max = period.date_to
                    p = period

        return p

    def _cancel_reserve_loop(self, i, balance):
        """Procedimiento que itera sobre las reservas hasta saldar la pérdida"""
        for reserve in self.env['account.reserve'].search([], order='type desc, priority asc, issue_date asc'):
            """Voy cancelando las reservas hasta que se haya absorbido todo el quebranto"""
            if not (i >= balance):
                i += reserve.amount
                reserve._action_cancel()  # Crea un asiento
                reserve.update({
                    'reduction_id': self.id,
                    'reduction_can': True,
                })
            else:
                break  # si salde todo el quebranto, paro

    def _cancel_capital_adjustment_loop(self, i, balance):
        if not (i >= balance):
            for adjustment in self.env['capital.adjustment'].search([], order='issue_date asc'):
                """Voy cancelando los ajustes hasta que se haya absorbido todo el quebranto"""
                if not (i >= balance):
                    i += adjustment.amount
                    adjustment._action_cancel()  # Crea un asiento
                    adjustment.update({
                        'reduction_id': self.id,
                        'reduction_can': True,
                    })
                else:
                    break  # si salde todo el quebranto, paro

    def _cancel_premium_loop(self, i, balance):
        if not (i >= balance):
            for share in self.env['account.share'].search([('partner_id', '=', self.partner_id), ('state', 'in', ['suscribed', 'integrated'])], order='state asc, date_of_issue asc'):
                """Voy cancelando las primas de las acciones hasta que se haya absorbido todo el quebranto"""
                if not (i >= balance):
                    i += share.issue_premium
                    share._action_cancel_premium()
                else:
                    break  # si salde todo el quebranto, paro

    def _cancel_suscribed_loop(self, i, balance, suscribed_value):
        if not (i >= balance):
            for share in self.env['account.share'].search([('partner_id', '=', self.partner_id), ('state', 'in', ['suscribed'])], order='state asc, date_of_issue asc'):
                """Voy cancelando las primas de las acciones hasta que se haya absorbido todo el quebranto"""
                if not (i >= balance):
                    suscribed_value += share.nominal_value
                    i += share.nominal_value
                else:
                    break  # si salde todo el quebranto, paro

    def _cancel_integrated_loop(self, i, balance, integrated_value):
        if not (i >= balance):
            for share in self.env['account.share'].search([('partner_id', '=', self.partner_id), ('state', 'in', ['integrated'])], order='state asc, date_of_issue asc'):
                """Voy cancelando las primas de las acciones hasta que se haya absorbido todo el quebranto"""
                if not (i >= balance):
                    integrated_value += share.nominal_value
                    i += share.nominal_value
                else:
                    break  # si salde todo el quebranto, paro

    @api.model
    def _default_cutoff_date(self):
        """obtiene la fecha de cierre por defecto"""
        today = fields.Date.context_today(self)
        company = self.env.company
        date_from, date_to = date_utils.get_fiscal_year(
            today,
            day=company.fiscalyear_last_day,
            month=int(company.fiscalyear_last_month),
        )
        if date_from:
            return date_from - relativedelta(days=1)
        else:
            return False

    def _compute_percentage_to_reduce(self, total_to_cancel=0):
        # calcular el total del capital - iterar sobre las acciones
        # Esta funcion quedo sin utilidad por ahora
        total_cap = 0
        for share in self.env['account.share'].search(['partner_id', '=', self.partner_id]):
            total_cap += share.nominal_value or 0
        percentage = (total_to_cancel/total_cap) if total_cap > 0 else 0
        return percentage

    def _compute_total_suscribed(self):
        self.ensure_one()
        total_suscribed = 0.0
        if len(self.shares) > 0:
            for share in self.shares:
                total_suscribed += share.nominal_value if share.state == 'suscribed' else 0.0
        return total_suscribed

    def _compute_total_integrated(self):
        self.ensure_one()
        total_integrated = 0.0
        if len(self.shares) > 0:
            for share in self.shares:
                total_integrated += share.nominal_value if share.state == 'integrated' else 0.0
        return total_integrated

    # LOW LEVELS METHODS
    @api.model
    def create(self, vals):
        if self.reduction_type == 'cancelation':
            raise UserError(
                'Las Cancelaciones deben crearse a partir de una Orden de Cancelación')
        if vals.get('short_name', _('New')) == _('New'):
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'capital.reduction') or _('New')
        res = super(ReductionOrder, self.create(vals))
        return res
    # CONSTRAINS

    @api.constrains('percentage_to_reduce')
    def _check_percentage(self):
        for record in self:
            if record.percentage_to_reduce > 1.0:
                raise ValidationError(
                    'El porcentaje a reducir no puede ser superior al 100%')
