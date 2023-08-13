# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import collections
import numpy
from functools import lru_cache
import hashlib
from itertools import groupby
import re
from time import time
from dateutil import relativedelta
from pytz import timezone, UTC
from markupsafe import escape, Markup
import requests
from odoo.exceptions import UserError
from werkzeug import urls

from datetime import datetime, timedelta
from werkzeug.urls import url_encode
from odoo.tools.float_utils import float_is_zero, float_compare, float_round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, format_amount, format_date, formatLang, get_lang, groupby
from odoo import SUPERUSER_ID, models, fields, api, tools

from odoo.osv.expression import get_unaccent_wrapper

from odoo.exceptions import ValidationError
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import math
import babel.dates
import logging

from odoo.addons.base.models.res_partner import _tz_get
from odoo.addons.calendar.models.calendar_attendee import Attendee
from odoo.addons.calendar.models.calendar_recurrence import weekday_to_field, RRULE_TYPE_SELECTION, END_TYPE_SELECTION, MONTH_BY_SELECTION, WEEKDAY_SELECTION, BYDAY_SELECTION
from odoo.tools.translate import _
from odoo.tools import pycompat
from odoo.exceptions import UserError, AccessError
# utilidades para calcular la TIR
# La lista flujos incluye el desembolso inicial


def VAN(tasa, flujos):
    VA = 0
    for j in range(len(flujos)):
        VA += flujos[j]/(1+tasa)**j
    return VA

# print('VAN=',VAN(0.05,[-4000,1400,1300,1200,1100]))


def TIR(flujos):
    ka = -.5  # tasa de descuento inferior. Inicialmente -50%
    kc = 10  # tasa de descuento superior. Inicialmente 1000%
    inf = VAN(ka, flujos)  # VAN calculado con la tasa inferior
    sup = VAN(kc, flujos)  # VAN calculado con la tasa superior
    if inf >= 0 and sup < 0:
        error = abs(inf-sup)
        while error >= 1e-10:
            kb = (ka+kc)/2
            # print(kb)
            med = VAN(kb, flujos)
            if med <= 0:
                kc = kb
            elif med > 0:
                ka = kb
            inf = VAN(ka, flujos)
            sup = VAN(kc, flujos)
            error = inf-sup
        return kb
    else:
        return 0


days = {
    'monthly': 30,
    'year': 365,
    'quarterly': 90,
    'bimonthly': 60
}


class AccountCertificate(models.Model):
    _name = 'account.certificate'
    _description = 'Orden de Emisión de Bonos'
    _rec_name = 'name'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _rec_names_search = ['name', 'ref']
    _order = 'priority desc, id desc'

    # métodos computados

    @api.depends('qty', 'issue_value')
    def _compute_nominal_value(self):
        for order in self:
            order.nominal_value = (
                order.qty * order.issue_value) - (order.fees_expenses)

    @api.depends('qty', 'refund_value')
    def _compute_final_value(self):
        for order in self:
            order.final_value = (order.qty * order.refund_value)

    @api.depends('certificates_ids')
    def _compute_invoice(self):
        for order in self:
            order.refunds_count = len(order.refunds_ids)

    @api.depends('certificates_ids')
    def _compute_refund(self):
        for order in self:
            order.certificate_count = len(order.certificates_ids)
    # calcular la tasa proporcional

    @api.depends('TNA')
    def _compute_proportional_rate(self):
        """Calcula la tasa proporcional de acuerdo al periodo
            seleccionado por el usuario.
        """
        self.ensure_one()
        # obtengo los valores de la seleccion como un diccionario

        pr = (self.TNA/365)*(float(days.get(self.compound_subperiod)))
        self.proportional_rate = pr
        self.interes_fee = (self.qty * self.issue_value) * pr
        return [pr]

    # Función para calcular la TIR
    @api.depends('qty', 'nominal_value', 'final_value', 'interes_fee')
    def _compute_TIR(self):
        for order in self:
            flow = [order.nominal_value]
            # itero sobre los flujos de interes
            for fee in range(order.qty):
                flow.append(order.interes_fee)
            flow.append(order.final_value)
            order.effective_rate = round(TIR(flow), 8)

    # BUSSINESS FIELDS

    name = fields.Char(string='Referencia', default='New',
                       required=True, copy=False, readonly=True)

    issue_date = fields.Date('Fecha de Emisión', default=fields.Date.today())
    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('approved', 'Aprobado'),
        ('confirm', 'Confirmado'),
        ('cancel', 'Cancelado'),
    ])
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Urgent')], 'Priority', default='0', index=True)
    # Campos relacionados
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company.id, readonly=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        tracking=True,
        required=True,
        store=True, readonly=False, precompute=True,
        states={'approved': [('readonly', True)], 'cancel': [
            ('readonly', True)]},
    )

    compound_subperiod = fields.Selection(string='Periodo de Capitalización', selection=[
        ('none', '---Seleccione una opción'),
        ('monthly', 'Mensual'),
        ('year', 'Anual'),
        ('quarterly', 'Trimestral'),
        ('bimonthly', 'Bimestral')
    ], required=True, default='none')
    TNA = fields.Float(string='Tasa Nominal Anual', default=0.0, required=True)
    effective_rate = fields.Float(string='Tasa Interna de Retorno',
                                  readonly=True, default=0.0, required=True, compute='_compute_TIR')

    interes_fee = fields.Monetary(
        string='Cuota de Interés', help='Cuota de interés explícito', readonly=True, default=0, compute='_compute_proportional_rate')

    proportional_rate = fields.Float(
        string='Tasa Proporcional', default=0.0, required=True, compute='_compute_proportional_rate', readonly=True)
    serial = fields.Integer(string='Nro. Serie')
    serial_total = fields.Monetary(string='Monto total de la serie')

    qty = fields.Integer(string='Cantidad', required=True)
    issue_value = fields.Float(string='Valor de cada Acción', required=True)
    refund_value = fields.Monetary(
        string='Valor de Reembolso', default=0, required=True)

    fees_expenses = fields.Monetary(
        string='Gastos de la Transacción', default=0)

    amortization = fields.Boolean(
        string='Amortización', default=True, readonly=True)
    expiration_date = fields.Date(
        string='Fecha de Vencimiento', default=fields.Date.today())

    nominal_value = fields.Float(
        string='Valor Nominal', readonly=True, compute='_compute_nominal_value', default=0)

    final_value = fields.Monetary(
        string='Valor Final', default=0, readonly=True, compute='_compute_final_value')

    periodic_interest = fields.Float(
        string='Interés Explícito', default=0.0, help='Indique la tasa nominal anual vigente en el mercado')

    cert_lines = fields.One2many(string='Líneas de Flujo de Efectivo',
                                 comodel_name='account.certificate.line', inverse_name='cert_order')
    certificates_ids = fields.Many2many(
        'account.move', string='Asientos', copy=False, store=True, domain=[('move_type', '=', 'certificate')])
    certificate_count = fields.Integer(
        compute="_compute_invoice", string='Bonos', copy=False, default=0, store=True)
    refunds_ids = fields.Many2many(
        'account.move', string='Asientos', copy=False, store=True, domain=[('move_type', '=', 'certificate_refund')])
    refunds_count = fields.Integer(
        compute="_compute_refund", string='Bonos', copy=False, default=0, store=True)
    user_id = fields.Many2one(
        'res.users', string='Operador', index=True, tracking=True,
        default=lambda self: self.env.user, check_company=True)

    partner_id = fields.Many2one(string='Comprador', comodel_name='res.partner',
                                 required=True, ondelete='cascade', readonly=True, index=True, store=True)
    notes = fields.Html(string='Notas')

    # metodos computados
    def button_set_new(self):
        for cert in self:
            if cert.state == 'draft':
                cert.state = 'new'

    def button_cancel(self):
        for cert in self:
            if cert.state not in ['confirm', 'cancel']:
                cert.state = 'cancel'
            else:
                raise UserError('No puede cancelarse el Bono')

    def button_approve(self):
        for cert in self:
            if cert.state == 'new':
                # crear el asiento contable para registrar el bono (emision del bono)
                cert.create_certificate()
                cert.state = 'approved'
            else:
                raise UserError('Acción no permitida - ')

    def button_confirm(self):
        for cert in self:
            if cert.state == 'approved' and cert.topic.state == 'approved':
                cert.create_flow_lines()
                cert.state = 'confirm'
            else:
                raise UserError('Acción no valida - (AC)')

    def action_draft(self):
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

    def action_refund(self):
        for cert in self:
            if cert.state == 'confirm':
                if cert._check_accrual_completition():
                    cert.create_refund()
                    cert.amortization = True
                    return {
                        'warning': {
                            'title': 'Listo!',
                            'message': 'Reembolso creado con éxito!'}
                    }
                else:
                    raise UserError('Aún quedan interes por devengar!.')

    def create_certificate(self):
        """Create the certificate associated to the IC.
        """

        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')
        # 0) Primero necesito saber cuantas ganancias liquidas tengo.
        # y cunto de reservas libres tengo
        # leer la cuenta para buscar el saldo
        account_financial_expenses = self.company_id.account_financial_expenses or self.env['account.account'].search([
            ('internal_type', '=', 'expenses_interest_and_implicit_financial_components')])[0]
        account_receivable_cert = self.partner_id.account_receivable_cert or self.company_id.account_receivable_cert or self.env['account.account'].search([
            ('internal_type', '=', 'asset_receivable')])[0]
        account_cert_payable = self.partner_id.account_cert_payable or self.company_id.account_cert_payable or self.env['account.account'].search([
            ('internal_type', '=', 'liability_payable')])[0]
        # leer el saldo y determianr su valor

        certificate_vals_list = []
        for order in self:
            if order.state != 'approved':
                continue

            order = order.with_company(order.company_id)
            # Invoice values.
            certificate_vals = order._prepare_certificate()
            # Invoice line values (asset ad product) (keep only necessary sections).

            expenses_line = {
                'account_id': (account_financial_expenses.id),
                'debit': order.fees_expenses or 0,
                'certificate_line_id': self.id
            }

            receivable_line = {
                'account_id': (account_receivable_cert.id),
                'credit': (order.nominal_value) or 0,
                'certificate_line_id': self.id
            }

            payable_line = {
                'account_id': account_cert_payable.id,
                'credit': (order.qty * order.issue_value) or 0,
                'partner_id': self.partner_id.id,
                'certificate_line_id': self.id
            }

            certificate_vals['line_ids'].extend(
                (0, 0, expenses_line), (0, 0, receivable_line), (0, 0, payable_line))

            certificate_vals_list.append(certificate_vals)

            # 3) Create invoices.
            SusMoves = self.env['account.move']
            AccountMove = self.env['account.move'].with_context(
                default_move_type='certificate')
            for vals in certificate_vals_list:
                SusMoves |= AccountMove.with_company(
                    vals['company_id']).create(vals)

            # 4) Some moves might actually be refunds: convert them if the totalamount     is         negative
            # We do this after the moves have been created since we need taxes, etc.to     know           if the total
            # is actually negative or not
            SusMoves.filtered(lambda m: m.currency_id.round(m.amount_total)
                              < 0).action_switch_invoice_into_refund_credit_note()
            return self.action_view_certificate(SusMoves)

    def _prepare_certificate(self):
        """Prepare the dict of values to create the new invoice for a purchase order.
        """
        self.ensure_one()
        move_type = self._context.get('default_move_type', 'certificate')

        partner_invoice = self.env['res.partner'].browse(
            self.partner_id.address_get(['invoice'])['invoice'])
        partner_bank_id = self.partner_id.commercial_partner_id.bank_ids.filtered_domain(
            ['|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)])[:1]

        invoice_vals = {
            'ref': self.serial or '',
            'move_type': move_type,
            'narration': self.notes,
            'invoice_user_id': self.user_id and self.user_id.id or self.env.user.id,
            'payment_reference': 'Referencia: %s (%s)' % (self.name, ',-"" '.join(self.partner_id)),
            'partner_bank_id': partner_bank_id.id,
            'invoice_origin': f"{self.name} - {self.issue_date}",
            'line_ids': [],
            'partner_id': self.partner_id.id,
            'certificate_id': self.id,
            'company_id': self.company_id.id,
        }
        return invoice_vals

    def _prepare_certificate_refund(self):
        """Prepare the dict of values to create the new invoice for a purchase order.
        """
        self.ensure_one()
        move_type = self._context.get(
            'default_move_type', 'certificate_refund')

        partner_invoice = self.env['res.partner'].browse(
            self.partner_id.address_get(['invoice'])['invoice'])
        partner_bank_id = self.partner_id.commercial_partner_id.bank_ids.filtered_domain(
            ['|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)])[:1]

        invoice_vals = {
            'ref': self.serial or '',
            'move_type': move_type,
            'narration': self.notes,
            'invoice_user_id': self.user_id and self.user_id.id or self.env.user.id,
            'payment_reference': 'Reintegro: %s (%s)' % (self.name, ',-"" '.join(self.partner_id, f"{fields.Date.today()}")),
            'partner_bank_id': partner_bank_id.id,
            'invoice_origin': f"{self.name} - {self.issue_date}",
            'line_ids': [],
            'partner_id': self.partner_id.id,
            'certificate_id': self.id,
            'company_id': self.company_id.id,
        }
        return invoice_vals

    def action_view_certificate(self, certificates=False):
        """This function returns an action that display existing  certificates entries of
        given certificate order ids. When only one found, show the certificate entries
        immediately.
        """
        if not certificates:
            # Invoice_ids may be filtered depending on the user. To ensure we get all
            # reductions related to the reduction order, we read them in sudo to fill the
            # cache.
            self.invalidate_model(['certificates_ids'])
            self.sudo()._read(['certificates_ids'])
            certificates = self.certificates_ids

        result = self.env['ir.actions.act_window']._for_xml_id(
            'higher_authority.action_move_in_account_certificate_type')
        # choose the view_mode accordingly
        if len(certificates) > 1:
            result['domain'] = [('id', 'in', certificates.ids)]
        elif len(certificates) == 1:
            res = self.env.ref(
                'higher_authority.view_certificate_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in result:
                result['views'] = form_view + \
                    [(state, view)
                     for state, view in result['views'] if view != 'form']
            else:
                result['views'] = form_view
            result['res_id'] = certificates.id
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result

    def create_flow_lines(self):
        """crea las lineas de flujo al aprobarse la orden de emision de bonos"""

        # debo crear una línea por cada cuota y una linea inicial y final
        # el numero de periodos dependerá de cauntos entran en el tiempo comprendido hasta el vencimiento del bono. para evitar inconvenientes en los periodos, los vencimientos se consideran a mes completo. (31 o 30 de cada mes)

        for order in self:
            # 0. preparo la linea inicial:
            amortized_cost = order.nominal_value

            # 1. cuento los dias hasta el vencimiento
            # ¿cuantas veces entra el subperiodo de cap. hasta el vencimiento?
            periods = maxPeriod = round((order.due_date-order.issue_date if order.due_date and order.due_date >
                                        order.issue_date else 0)/days.get(order.compound_subperiod), 0)
            for period in range(periods+1):
                implicit_interest = (
                    amortized_cost * order.effective_rate)-(order.interes_fee)
                flow_line = order.prepare_flow_lines()
                flow_line.update({
                    'due_date': f'{order.issue_date + (days.get(order.compound_subperiod)*period)}',
                    'number': period,
                    'state': 'draft',
                    'interes_total': f'{amortized_cost * order.effective_rate}',
                    'implicit_interest': f'{implicit_interest}',
                    'amortized_cost': f'{amortized_cost+implicit_interest}',
                })
                if period == maxPeriod:
                    flow_line.update({
                        # continuar por aquí!
                    })
                self.env['account.certificate.line'].create(flow_line)
                amortized_cost += implicit_interest

    def prepare_flow_lines(self):
        flow_vals = {
            'name': '',
            'ref': f'{self.name} - {self.issue_date}',
            'due_date': '',
            'number': '',
            'state': 'draft',
            'interes_total': '',
            'interest_fee': f'{self.interes_fee}',
            'implicit_interest': '',
            'amortized_cost': '',
            'cert_order': f'{self.id}',
        }
        return flow_vals

    def _check_accrual_completition(self):
        self.ensure_one()
        lines = self.cert_lines
        if len(lines) > 0:
            if not all([self.check_and_break(line) for line in lines]):
                # si todas las lineas fueron devengadas
                # procedo a la liquidacion final
                return False
            return True
        return False

    def check_and_break(self, line):
        return line.state == 'accrued'

    def create_refund(self):
        """Crea el reembolso del bono! lo unico que debemos hacer aquí es crear un pago 
            a partir del asiento que crea el bono y que el pago cancele el bono en su totalidad.

        """
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')

        account_cert_amortized = self.partner_id.account_cert_amortized or self.company_id.account_cert_amortized or self.env['account.account'].search([
            ('internal_type', '=', 'liability_payable_amortized')])[0]
        account_cert_payable = self.partner_id.account_cert_payable or self.company_id.account_cert_payable or self.env['account.account'].search([
            ('internal_type', '=', 'liability_payable')])[0]

        certificate_vals_list = []
        for order in self:
            if order.state != 'confirm':
                continue

            order = order.with_company(order.company_id)
            # Invoice values.
            certificate_vals = order._prepare_certificate_refund()
            # Invoice line values (asset ad product) (keep only necessary sections).

            amortized_line = {
                'account_id': (account_cert_amortized.id),
                'credit': (order.final_value) or 0,
                'partner_id': self.partner_id.id
            }

            payable_line = {
                'account_id': (account_cert_payable.id),
                'debit': order.final_value or 0,
                'partner_id': self.partner_id.id
            }

            certificate_vals['line_ids'].extend([
                (0, 0, amortized_line), (0, 0, payable_line)])

            certificate_vals_list.append(certificate_vals)

            # 3) Create invoices.
            SusMoves = self.env['account.move']
            AccountMove = self.env['account.move'].with_context(
                default_move_type='certificate_refund')
            for vals in certificate_vals_list:
                SusMoves |= AccountMove.with_company(
                    vals['company_id']).create(vals)

            # 4) Some moves might actually be refunds: convert them if the totalamount     is         negative
            # We do this after the moves have been created since we need taxes, etc.to     know           if the total
            # is actually negative or not
            SusMoves.filtered(lambda m: m.currency_id.round(m.amount_total)
                              < 0).action_switch_invoice_into_refund_credit_note()

            return self.action_view_certificate_refund(SusMoves)

#    CREAR ACA LA ACCION PARA VER LOS ASIENTOS
    def action_view_certificate_refund(self, refunds=False):
        """This function returns an action that display existing  certificates entries of
        given certificate order ids. When only one found, show the certificate entries
        immediately.
        """
        if not refunds:
            # Invoice_ids may be filtered depending on the user. To ensure we get all
            # reductions related to the reduction order, we read them in sudo to fill the
            # cache.
            self.invalidate_model(['certificates_ids'])
            self.sudo()._read(['certificates_ids'])
            certificates = self.certificates_ids

        result = self.env['ir.actions.act_window']._for_xml_id(
            'higher_authority.action_move_in_account_certificate_type')
        # choose the view_mode accordingly
        if len(certificates) > 1:
            result['domain'] = [('id', 'in', certificates.ids)]
        elif len(certificates) == 1:
            res = self.env.ref(
                'higher_authority.view_certificate_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in result:
                result['views'] = form_view + \
                    [(state, view)
                     for state, view in result['views'] if view != 'form']
            else:
                result['views'] = form_view
            result['res_id'] = certificates.id
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'account.certificate') or _('New')
        res = super(AccountCertificate, self.create(vals))
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_if_cancelled(self):
        for order in self:
            if not order.state == 'cancel':
                raise UserError(
                    _('In order to delete a certificate order, you must cancel it first.'))


class AccountCertificateLine(models.Model):
    _name = 'account.certificate.line'
    _description = 'Líneas de Emisión de Bonos'
    _rec_name = 'name'
    # _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _rec_names_search = ['name']
    _order = 'name desc, id desc'

    name = fields.Char(string='Referencia', default='New',
                       required=True, copy=False, readonly=True)
    ref = fields.Char(string='Código')
    due_date = fields.Date(string='Fecha de Vencimiento')
    number = fields.Integer(
        string='Período', readonly=True, default=0, required=True)

    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('accrued', 'Devengado'),
        ('cancel', 'Cancelado')
    ])

    interes_total = fields.Monetary(string='Interés Total')
    interest_fee = fields.Monetary(string='Interés Explícito')
    implicit_interest = fields.Monetary(string='Interés Implícito')

    amortized_cost = fields.Monetary(
        string='Costo Amortizado', readonly=True, default=0, required=True)

    cert_order = fields.Many2one(string='Orden de Emisión', comodel_name='account.certificate',
                                 required=True, readonly=True, store=True, index=True, copy=True)

    certificates_line_ids = fields.Many2many(
        'account.move', 'certificate_line_id', string='Asiento', readonly=True, copy=False)
    certificate_line_count = fields.Integer(
        compute="_compute_invoice", string='Bonos', copy=False, default=0, store=True)
    

    # este modelo tendra un boton para registrar el devengamiento de los pagos
    # de intereses - lo cual creará el asiento contable correspondiente.

    # {
    #     'name':'',
    #     'due_date':'',
    #     'number':'',
    #     'state':'',
    #     'interes_total':'',
    #     'interest_fee':'',
    #     'implicit_interest':'',
    #     'amortized_cost':'',
    #     'cert_order':'',
    # }
    
    # metodos computados
    @api.depends('certificates_ids')
    def _compute_invoice(self):
        for order in self:
            order.certificate_line_count = len(order.certificates_line_ids)

    def button_set_new(self):
        for cert in self:
            if cert.state == 'draft':
                cert.state = 'new'

    def button_confirm(self):
        for cert in self:
            if cert.state == 'new':
                cert.create_accrued_fee()
                cert.state = 'accrued'
            else:
                raise UserError('Acción no valida - (AC)')

    def action_draft(self):
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

    def button_cancel(self):
        for cert in self:
            if cert.state not in ['accrued', 'cancel']:
                cert.state = 'cancel'
            else:
                raise UserError('No puede cancelarse la línea')

    def action_view_certificate_line(self, certificates=False):
        """Accion que permite ver el asiento asociado"""
        if not certificates:
            # Invoice_ids may be filtered depending on the user. To ensure we get all
            # reductions related to the reduction order, we read them in sudo to fill the
            # cache.
            self.invalidate_model(['certificates_ids'])
            self.sudo()._read(['certificates_ids'])
            certificates_line = self.certificates_line_ids

        result = self.env['ir.actions.act_window']._for_xml_id(
            'higher_authority.action_move_in_certificate_line_type')
        # choose the view_mode accordingly
        if len(certificates_line) > 1:
            result['domain'] = [('id', 'in', certificates_line.ids)]
        elif len(certificates_line) == 1:
            res = self.env.ref(
                'higher_authority.view_certificate_line_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in result:
                result['views'] = form_view + \
                    [(state, view)
                     for state, view in result['views'] if view != 'form']
            else:
                result['views'] = form_view
            result['res_id'] = certificates_line.id
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result

    def create_accrued_fee(self):
        """Create the certificate associated to the IC.
        """
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')
        # 0) Primero necesito saber cuantas ganancias liquidas tengo.
        # y cunto de reservas libres tengo
        # leer la cuenta para buscar el saldo

        account_cert_interest = self.partner_id.account_cert_interest or self.company_id.account_cert_interest or self.env['account.account'].search([
            ('internal_type', '=', 'expenses_interest_and_implicit_financial_components')])[0]
        account_cert_payable = self.partner_id.account_cert_payable or self.company_id.account_cert_payable or self.env['account.account'].search([
            ('internal_type', '=', 'liability_payable')])[0]
        # leer el saldo y determianr su valor

        certificate_vals_list = []
        for line in self:
            if line.state != 'new':
                continue

            line = line.with_company(line.company_id)
            # Invoice values.
            certificate_vals = line._prepare_fee()
            # Invoice line values (asset ad product) (keep only necessary sections).

            interes_line = {
                'account_id': (account_cert_interest.id),
                'debit': self.interes_total or 0,
                'partner_id': self.partner_id.id
            }

            payable_line = {
                'account_id': account_cert_payable.id,
                'credit': self.interes_total or 0,
                'partner_id': self.partner_id.id
            }

            certificate_vals['line_ids'].extend([
                (0, 0, interes_line), (0, 0, payable_line)])

            certificate_vals_list.append(certificate_vals)

            # 3) Create invoices.
            SusMoves = self.env['account.move']
            AccountMove = self.env['account.move'].with_context(
                default_move_type='certificate_line')
            for vals in certificate_vals_list:
                lineMove = AccountMove.with_company(
                    vals['company_id']).create(vals)
                SusMoves |= lineMove
                line.certificates_line_ids |= lineMove

            # 4) Some moves might actually be refunds: convert them if the totalamount     is         negative
            # We do this after the moves have been created since we need taxes, etc.to     know           if the total
            # is actually negative or not
            SusMoves.filtered(lambda m: m.currency_id.round(m.amount_total)
                              < 0).action_switch_invoice_into_refund_credit_note()
            return self.action_view_certificate_line(SusMoves)

    def _prepare_fee(self):
        """Prepare the dict of values to create the new invoice for a purchase order.
        """
        self.ensure_one()
        move_type = self._context.get('default_move_type', 'certificate')

        partner_invoice = self.env['res.partner'].browse(
            self.partner_id.address_get(['invoice'])['invoice'])
        partner_bank_id = self.cert_order.partner_id.commercial_partner_id.bank_ids.filtered_domain(
            ['|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)])[:1]

        invoice_vals = {
            'ref': self.name or '',
            'move_type': move_type,
            'invoice_user_id': self.cert_order.user_id and self.cert_order.user_id.id or self.env.user.id,
            'payment_reference': 'Referencia: %s (%s)' % (self.name, ',-"" '.join(self.due_date)),
            'partner_bank_id': partner_bank_id.id,
            'invoice_origin': f"{self.name} - {self.due_date}",
            'line_ids': [],
            'company_id': self.cert_order.company_id.id,
        }
        return invoice_vals
