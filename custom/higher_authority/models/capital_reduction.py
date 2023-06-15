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


class reductionOrder(models.Model):
    _name = 'capital.reduction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Objeto Reducción de Acciones'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'

    # metodos computados
    @api.depends('reduction_type', 'loss_absortion')
    def _compute_total(self):
        for red in self:
            if red.reduction_type == 'voluntary':
                red.reduction_amount = self.manual_amount
            elif red.reduction_type == 'cancelation':
                red.reduction_amount = self._compute_total_to_cancel()

    short_name = fields.Char(string='Referencia', default='New',
                             required=True, copy=False, readonly=True)
    name = fields.Char(string='Nombre', required=True, tracking=True)
    date = fields.Date(string='Fecha de Confección')
    date_due = fields.Date(
        string='Fecha de vencimiento', help='Coloque aquí la fecha estimada de integración', states={'draft': [('readonly', False)]})

    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('confirm', 'Confirmado'),
        ('cancel', 'Cancelado')
    ], default='draft')
    reduction_type = fields.Selection(string='Tipo', selection=[
        ('voluntary', 'Voluntaria'),
        ('obligatory', 'Obligatoria'),
        ('cancelation', 'Cancelación de Acciones'),
    ], default='voluntary')
    reduction_ids = fields.Many2many(
        'account.move', string='Reducciones', copy=False, store=True)
    shares = fields.One2many(string='Acciones a Cancelar', help='Acciones creadas',
                             comodel_name='account.share', inverse_name='share_issuance', index=True, domain="[('state','not in',('canceled','draft','new'))]")

    # loss_absortion = fields.Boolean(
    #     string='Absorción de Pérdidas', default=False)
    manual_amount = fields.Monetary(
        string='Cantidad Manual', help='Indique la cantidad a reducir, cuando el tipo de reducción sea - voluntaria (para absorber pérdidas)')
    reduction_amount = fields.Monetary(
        string='Total', compute='_compute_total', readonly=True)

    notes = fields.Text(string='Notas')

    shareholder_id = fields.Many2one(
        string='Accionista', comodel_name='account.shareholder', required=True)
    capital_reduction_group = fields.Many2one(
        string='Componente de Reducción', comodel_name='capital.reducton.type')
    reduction_count = fields.Integer(
        compute="_compute_invoice", string='Reducciones', copy=False, default=0, store=True)
    user_id = fields.Many2one('res.users', string='Empleado',
                              index=True, tracking=True, default=lambda self: self.env.user)
    @api.depends('reduction_ids')
    def _compute_invoice(self):
        for order in self:
            reductions = order.reduction_ids
            order.invoice_count = len(order.reduction_ids)

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
    def button_confirm(self):
        for red in self:
            if red.state == 'new':
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
    # logica

    def action_create_reduction_vol(self):
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
        """Create the reduction associated to the SO.
        """
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')

        # a- calcular el maximo importe que se podrá reducir para este accionista
        max_to_red = self._compute_max_to_red()
        # b- seleccionar las acciones a cancelar,
        # c- sumar el total a cancelar
        total_to_cancel = self._compute_total_to_cancel()
        # d- verificar si el total a cancelar no supere el maximo importe
        if total_to_cancel > max_to_red:
            raise UserError(f'El total a cancelar supera el monto máximo permitido: ${max_to_red}'.format(
                max_to_red=max_to_red))

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
                'debit': self.reduction_amount or 0,
            }
            credit_line = {
                'display_type': 'line_note',
                'account_id': self.capital_reduction_group.profit_lost_account.id,
                'credit': self.reduction_amount or 0,
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
        # e- dar de baja las acciones
        self._action_cancel_shares()
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
            pending_section = None
            # Invoice values.
            reduction_vals = order._prepare_reduction()
            # Invoice line values (asset ad product) (keep only necessary sections).


            # algoritmo para calcular esto

            # 1- sumar los conceptos correspondientes (acceder al modelo de share y sumar su valor total [nominal + prima] y AI)
                
            # 2- Determinar el resultado del ejercicio (31/12 del ejercicio cerrado)
                # - si es pérdida: se procede al calculo
                #   - compr0bar si insume el 50% del capital
                # - si el resultado es positivo: se lanza raise UserError('')

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

    def _compute_max_to_red(self):
        self.ensure_one()
        max_to_red = 0
        for share in self.shareholder_id.shares:
            max_to_red += share.price if share.state == 'subscribed' else 0
        return max_to_red

    def _prepare_reduction(self):
        """Prepare the dict of values to create the new invoice for a purchase order.
        """
        self.ensure_one()
        move_type = self._context.get('default_move_type', 'reduction')

        partner_invoice = self.env['res.partner'].browse(
            self.shareholder_id.partner_id.address_get(['invoice'])['invoice'])
        partner_bank_id = self.shareholder_id.partner_id.commercial_partner_id.bank_ids.filtered_domain(
            ['|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)])[:1]

        reduction_vals = {
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
        for share in self.shareholder_id.shares:
            if share.state == 'suscribed':
                total_to_cancel += share.price
        self.reduction_amount = total_to_cancel
        return total_to_cancel

    def _action_cancel_shares(self):
        for red in self:
            for share in red.shareholder_id.shares:
                share.share_cancel()
