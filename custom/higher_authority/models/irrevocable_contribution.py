# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

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

from odoo.osv.expression import get_unaccent_wrapper

from odoo.addons.base.models.res_partner import _tz_get
from odoo.addons.calendar.models.calendar_attendee import Attendee
from odoo.addons.calendar.models.calendar_recurrence import weekday_to_field, RRULE_TYPE_SELECTION, END_TYPE_SELECTION, MONTH_BY_SELECTION, WEEKDAY_SELECTION, BYDAY_SELECTION
from odoo.tools.translate import _
from odoo.tools.misc import get_lang
from odoo.tools import pycompat
from odoo.exceptions import UserError, AccessError, ValidationError


class IrrevocableContribution(models.Model):
    _name = 'irrevocable.contribution'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    # _inherits = {'calendar.event': 'event_id'}
    _description = 'Objeto Aporte Irrevocable'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'

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

    short_name = fields.Char(string='Referencia', default='New',
                             required=True, copy=False, readonly=True)
    name = fields.Char(string='Título', copy=False)
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Urgent')], 'Priority', default='0', index=True)
    date = fields.Date(string='Fecha', required=True,
                       default=fields.datetime.now)
    type = fields.Selection(string='Tipo', help='Escoga el tipo de aporte', selection=[(
        'future', 'Para Futuras Suscripciones'), ('loss', 'Para Absorber Pérdidas Acumuladas')], default='future')
    partner_id = fields.Many2one(
        string='Accionista', comodel_name='res.partner')
    date_due = fields.Date(string='Fecha Límite de integración', required=True)
    integration_date = fields.Date(
        string='Fecha de Integración', readonly=True)
    amount = fields.Monetary(string='Monto del Aporte',
                             required=True, default=0)
    user_id = fields.Many2one(
        'res.users', string='Operador', index=True, tracking=True,
        default=lambda self: self.env.user, check_company=True)

    origin = fields.Char(string='Documento')

    is_meeting = fields.Boolean(string='Tratado en Reunión')
    is_integrated = fields.Boolean(string='Integrado')

    share_issuance = fields.Many2one(
        string='Emisión', comodel_name='share.issuance', readonly=True, help='Emisión de Acciones Relacionada')

    contribution_count = fields.Integer(
        compute="_compute_contribution", string='Cantidad de Asientos', copy=False, default=0, store=True)
    contribution_ids = fields.Many2many(
        'account.move', string='Asientos', copy=False, store=True)
    integration_count = fields.Integer(
        compute="_compute_integration", string='Cantidad de Asientos', copy=False, default=0, store=True)
    integration_ids = fields.Many2many(
        'account.move', string='Asientos', copy=False, store=True)

    state = fields.Selection(string='Estado', selection=[('draft', 'Borrador'), ('new', 'Nuevo'), (
        'approved', 'Aprobado'), ('confirm', 'Confirmado'), ('cancel', 'Cancelado')])

    fiscal_position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position',
                                         domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    notes = fields.Html(string='Descripción')
    topic = fields.Many2one(string='Tema de Reunión',
                            comodel_name='assembly.meeting.topic', ondelete='restrict', readonly=True)

    # low level methods

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'irrevocable.contribution') or 'New'
        res = super(IrrevocableContribution, self.create(vals))
        return res

    # def button_set_new(self):
    #     for cont in self:
    #         if cont.state == 'draft':
    #             cont.state = 'new'
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
            if cont.state not in ['draft', 'cancel', 'confirm', 'approved'] & cont.topic.state=='approved':
                cont.action_create_contribution()
                cont._action_create_share_issuance()
                cont.state = 'approved'
            else:
                raise UserError('Orden de emision no autorizada')

    def action_cancel(self):
        for cont in self:
            if cont.state not in ['draft', 'new', 'cancel','confirm'] and cont.topic.id.state == 'refused':
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
        property_account_contribution_credits_id = self.partner_id.property_account_contribution_credits_id or self.company_id.property_account_contribution_credits_id or self.env['account.account'].search([
            ('internal_type', '=', 'property_account_contribution_credits_id')])[0]
        property_account_contribution_id = self.partner_id.property_account_contribution_id or self.company_id.property_account_contribution_id or self.env['account.account'].search([
            ('internal_type', '=', 'contribution')])[0]

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
            credit_line = {
                'account_id': property_account_contribution_id,
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
        property_account_integration_id = self.partner_id.property_account_integration_id or self.company_id.property_account_integration_id or self.env['account.account'].search([
            ('internal_type', '=', 'equity')])[0]
        property_account_contribution_id = self.partner_id.property_account_contribution_id or self.company_id.property_account_contribution_id or self.env['account.account'].search([
            ('internal_type', '=', 'contribution')])[0]

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
            debit_line = {
                'account_id': property_account_contribution_id,
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
        property_account_contribution_credits_id = self.partner_id.property_account_contribution_credits_id or self.company_id.property_account_contribution_credits_id or self.env['account.account'].search([
            ('internal_type', '=', 'property_account_contribution_credits_id')])[0]
        property_account_contribution_id = self.partner_id.property_account_contribution_id or self.company_id.property_account_contribution_id or self.env['account.account'].search([
            ('internal_type', '=', 'contribution')])[0]
        # 1) Prepare suscription vals and clean-up the section lines
        contribution_vals_list = []
        for order in self:
            if order.state != 'approved':
                continue

            order = order.with_company(order.company_id)
            # Invoice values.
            contribution_vals = order._prepare_contribution()
            # Invoice line values (asset ad product) (keep only necessary sections).

            debit_line = {
                'account_id': property_account_contribution_id,
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
            'fiscal_position_id': (self.fiscal_position_id or self.fiscal_position_id._get_fiscal_position(partner_invoice)).id,
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
        partner_bank_id = self.partner_id.commercial_partner_id.bank_ids.filtered_domain(['|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)])[:1]

        invoice_vals = {
            'ref': self.partner_ref or '',
            'contribution_id':self.id,
            'move_type': move_type,
            'narration': self.notes,
            'currency_id': self.currency_id.id,
            'invoice_user_id': self.user_id and self.user_id.id or self.env.user.id,
            'partner_id': partner_invoice.id,
            'fiscal_position_id': (self.fiscal_position_id or self.fiscal_position_id._get_fiscal_position(partner_invoice)).id,
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
            ser tratada por la asamblea
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
