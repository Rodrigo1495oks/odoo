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


class PortfolioShares(models.Model):
    _name = 'portfolio.shares'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Objeto Acciones en Cartera'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'

    short_name = fields.Char(string='Referencia', default='New',
                             required=True, copy=False, readonly=True)
    name = fields.Char(string='Nombre', required=True, tracking=True)
    date = fields.Date(string='Fecha de Confección')

    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('approved', 'Aprobado'),
        ('confirm', 'Confirmado'),
        ('cancel', 'Cancelado')
    ], default='draft', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company.id)
    redemption_ids = fields.Many2many(
        'account.move', string='Reducciones', copy=False, store=True)
    redemption_count = fields.Integer(
        compute="_compute_invoice", string='Reducciones', copy=False, default=0, store=True)
    shares = fields.One2many(string='Acciones a Cancelar', help='Acciones creadas',
                             comodel_name='account.share', inverse_name='portfolio_shares', index=True, domain=[('state', 'in', ('integrated'), ('partner_id', '=', 'partner_id'))], compute='_compute_shares_to_portfolio')
    topic = fields.Many2one(
        string='Tópico', comodel_name='assembly.meeting.topic', readonly=True)
    user_id = fields.Many2one('res.users', string='Empleado',
                              index=True, tracking=True, default=lambda self: self.env.user)
    partner_id = fields.Many2one(
        string='Accionista', comodel_name='res.partner', required=True)
    notes = fields.Html(string='Descripción')

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
            if red.state == 'new':
                topic_vals = self._prepare_topic_values()
                self.env['assembly.meeting.topic'].create(topic_vals)
                red.state = 'approved'
            else:
                raise UserError('Acción no permitida - ')

    def button_confirm(self):
        for red in self:
            if red.state == 'approved' and red.topic.state == 'approved':
                red.create_redemption()
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

    def _prepare_topic_values(self):
        self.ensure_one()
        topic_values = {
            "name": f"Rescate de Acciones: .-/ {self.date} \n",
            "description": f"Rescate de Acciones: {self.notes}",
            "state": "draft",
            "topic_type": "redemption",
        }
        return topic_values

    def create_redemption(self):
        """Create the redemption associated to the IC.
        """
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')
        # 0) Primero necesito saber cuantas ganancias liquidas tengo.
        # y cunto de reservas libres tengo
        # leer la cuenta para buscar el saldo
        period = self._return_last_fiscal_year()
        result_account = self.env['ir.config_parameter'].get_param(
            'higher_authority.financial_year_result_account')
        account_payable_redemption = self.env['ir.config_parameter'].get_param(
            'higher_authority.account_payable_redemption')

        # leer el saldo y determianr su valor

        balance = -(float(self.check_balance(result_account, period.date_to)))

        total_liquid = 0
        total_to_redempt = 0

        for share in self.shares:
            total_to_redempt += share.nominal_value

        if balance > 0.0:  # si hay ganancia al cierre del ejercicio
            # voy a iterar sobre todas las cuentas de efectivo
            for account in self.env['account.account'].search():
                if account.account_type == 'asset_cash':
                    total_liquid += (float(self.check_balance(account,
                                     fields.Date.today())))
            # corroborar si hay suficiente efectivo
            if total_liquid > 0.0 and total_liquid >= total_to_redempt:
                # 1) Prepare suscription vals and clean-up the section lines
                redemption_vals_list = []
                for order in self:
                    if order.state != 'approved':
                        continue

                    order = order.with_company(order.company_id)
                    # Invoice values.
                    redemption_vals = order._prepare_redemption()
                    # Invoice line values (asset ad product) (keep only necessary sections).

                    total_integrated = self._compute_total_integrated()
                    total_issue_discount = self._compute_total_issue_discount()
                    total_issue_premium = self._compute_total_issue_premium()

                    integrated_line = {
                        'display_type': 'line_note',
                        'account_id': (self.env['ir.config_parameter'].get_param(
                            'higher_authority.property_account_integration_id').id),
                        'debit': total_integrated or 0,
                    }

                    capital_line = {
                        'display_type': 'line_note',
                        'account_id': (self.env['ir.config_parameter'].get_param(
                            'higher_authority.property_account_portfolio_shares').id),
                        'credit': (total_integrated) or 0,
                    }
                    result_debit_line = {
                        'display_type': 'line_note',
                        'account_id': (result_account).id,
                        'debit': (sum(total_integrated+total_issue_premium)-total_issue_discount) or 0,
                    }
                    payable_line = {
                        'display_type': 'line_note',
                        'account_id': (account_payable_redemption).id,
                        'credit': (sum(total_integrated+total_issue_premium)-total_issue_discount) or 0,
                        'partner_id': self.partner_id.partner_id.id
                    }

                    redemption_vals['line_ids'].append(
                        (0, 0, integrated_line))
                    redemption_vals['line_ids'].append(
                        (0, 0, capital_line))
                    redemption_vals['line_ids'].append(
                        (0, 0, result_debit_line))
                    redemption_vals['line_ids'].append(
                        (0, 0, payable_line))

                    redemption_vals_list.append(redemption_vals)

                    # 2 bis)  cambiar el estado de las acciones a 'portfolio'
                    for share in order.share:
                        share.action_portfolio()

                    # 3) Create invoices.
                    SusMoves = self.env['account.move']
                    AccountMove = self.env['account.move'].with_context(
                        default_move_type='redemption')
                for vals in redemption_vals_list:
                    SusMoves |= AccountMove.with_company(
                        vals['company_id']).create(vals)

                # 4) Some moves might actually be refunds: convert them if the total amount     is         negative
                # We do this after the moves have been created since we need taxes, etc. to     know           if the total
                # is actually negative or not
                SusMoves.filtered(lambda m: m.currency_id.round(m.amount_total)
                                  < 0).action_switch_invoice_into_refund_credit_note()

                return self.action_view_redemption(SusMoves)
            else:
                UserError(
                    'No puede rescatarse las acciones seleccionadas porque los fondos no son suficientes')

        else:
            raise UserError(
                'El último ejercicio cerrado no ha presentado ganancias')

    def _prepare_redemption(self):
        """Prepare the dict of values to create the new invoice for a purchase order.
        """
        self.ensure_one()
        move_type = self._context.get('default_move_type', 'redemption')

        partner_invoice = self.env['res.partner'].browse(
            self.partner_id.address_get(['invoice'])['invoice'])
        partner_bank_id = self.partner_id.commercial_partner_id.bank_ids.filtered_domain(
            ['|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)])[:1]

        invoice_vals = {
            'ref': self.partner_ref or '',
            'move_type': move_type,
            'narration': self.notes,
            'invoice_user_id': self.user_id and self.user_id.id or self.env.user.id,
            'fiscal_position_id': (self.fiscal_position_id or self.fiscal_position_id._get_fiscal_position(partner_invoice)).id,
            'payment_reference': self.partner_ref or '',
            'partner_bank_id': partner_bank_id.id,
            'invoice_origin': f"{self.short_name} - {self.date}",
            'line_ids': [],
            'company_id': self.company_id.id,
        }
        return invoice_vals

    def action_view_redemption(self, redemptions=False):
        """This function returns an action that display existing  redemptions entries of
        given redemption order ids. When only one found, show the redemption entries
        immediately.
        """
        if not redemptions:
            # Invoice_ids may be filtered depending on the user. To ensure we get all
            # reductions related to the reduction order, we read them in sudo to fill the
            # cache.
            self.invalidate_model(['redemptions_ids'])
            self.sudo()._read(['redemptions_ids'])
            redemptions = self.redemption_ids

        result = self.env['ir.actions.act_window']._for_xml_id(
            'higher_authority.action_move_in_redemption_type')
        # choose the view_mode accordingly
        if len(redemptions) > 1:
            result['domain'] = [('id', 'in', redemptions.ids)]
        elif len(redemptions) == 1:
            res = self.env.ref('higher_authority.view_redemption_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in result:
                result['views'] = form_view + \
                    [(state, view)
                     for state, view in result['views'] if view != 'form']
            else:
                result['views'] = form_view
            result['res_id'] = redemptions.id
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result

    def _compute_total_integrated(self):
        self.ensure_one()
        total_integrated = 0
        if len(self.shares) > 0:
            for share in self.shares:
                total_integrated += share.nominal_value if share.state == 'integrated' else 0
        return total_integrated

    def _compute_total_issue_premium(self):
        self.ensure_one()
        total_integrated = 0
        if len(self.shares) > 0:
            for share in self.shares:
                total_integrated += share.issue_premium if share.state == 'integrated' else 0
        return total_integrated

    def _compute_total_issue_discount(self):
        self.ensure_one()
        total_integrated = 0
        if len(self.shares) > 0:
            for share in self.shares:
                total_integrated += share.issue_discount if share.state == 'integrated' else 0
        return total_integrated

    def _return_last_fiscal_year(self):
        periods = self.env['account.fiscal.year'].search(
        )

        max = 0
        p = ''
        # selecciono el periodo mas reciente (ultimo ejercicio cerrado)
        for period in periods:
            if period.date <= self.date:
                if period.date_to >= max:
                    max = period.date_to
                    p = period

        return p
     # low level methods
    #  COMPUTE METHODS

    @api.depends('redemption_ids')
    def _compute_invoice(self):
        for order in self:
            order.redemption_count = len(order.redemption_ids)

    @api.depends('partner_id')
    def _compute_shares_to_portfolio(self):
        """Obtiene todas las acciones que se encuentran en estado integrated y que aún no tengan ninguna orden de rescate de acciones en cartera, filtrados por el accionista"""

        shares = self.env['account.share'].search([
            ('partner_id', 'in', self.partner_id), ('state', 'in', ('integrated'))
        ])
        for order in self:
            order.shares = shares.filtered(
                lambda share: not share.portfolio_shares)

    @api.model
    def create(self, vals):
        if vals.get('short_name', _('New')) == _('New'):
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'portfolio.shares') or _('New')
        res = super(PortfolioShares, self.create(vals))
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_if_cancelled(self):
        for order in self:
            if not order.state == 'cancel':
                raise UserError(
                    _('In order to delete a purchase order, you must cancel it first.'))
