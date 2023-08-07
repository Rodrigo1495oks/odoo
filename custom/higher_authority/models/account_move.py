import ast
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta
from functools import lru_cache

from odoo import api, fields, models, Command, _
from odoo.tools import frozendict, formatLang, format_date, float_compare, Query
from odoo.tools.sql import create_index
from odoo.addons.web.controllers.utils import clean_action

from odoo.addons.account.models.account_move import MAX_HASH_VERSION

# -*- coding: utf-8 -*-

from collections import defaultdict
from contextlib import ExitStack, contextmanager
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from hashlib import sha256
from json import dumps
import re
from textwrap import shorten
from unittest.mock import patch


from odoo.addons.base.models.decimal_precision import DecimalPrecision
from odoo.addons.account.tools import format_rf_reference
from odoo.exceptions import UserError, ValidationError, AccessError, RedirectWarning
from odoo.tools import (
    date_utils,
    email_re,
    email_split,
    float_compare,
    float_is_zero,
    float_repr,
    format_amount,
    format_date,
    formatLang,
    frozendict,
    get_lang,
    is_html_empty,
    sql
)


MAX_HASH_VERSION = 3

TYPE_REVERSE_MAP = {
    'entry': 'entry',
    'out_invoice': 'out_refund',
    'out_refund': 'entry',
    'in_invoice': 'in_refund',
    'in_refund': 'entry',
    'out_receipt': 'entry',
    'in_receipt': 'entry',
}

EMPTY = object()


class AccountMove(models.Model):
    # _name = "account.move"
    _inherit = "account.move"

    move_type = fields.Selection(
        selection_add=[
            ('suscription', 'Suscription'),
            ('integration', 'Integration'),
            ('contribution', 'Aporte Irrevocable'),
            ('redemption', 'Rescate de Acciones'),
            ('share_sale', 'Venta de Acciones'),
            ('reduction', 'Reducción de Capital'),
            ('certificate', 'Emision de Bonos'),
            ('certificate_line', 'Líneas de Bonos'),
            ('certificate_refund', 'Líneas de Bonos')
        ]
    )
    # Campos para los bonos

    certificate_id = fields.Many2one(
        string='Bono', comodel_name='account.certificate', store=False, readonly=True,
        states={'draft': [('readonly', False)]})
    certificate_count = fields.Integer(
        compute="_compute_origin_certificate_count", string='Integration Order Count')
    # lineas de bonos
    certificate_line_id = fields.Many2one(
        string='Líneas de Bono', comodel_name='account.certificate.line', store=False, readonly=True,
        states={'draft': [('readonly', False)]})
    certificate_count = fields.Integer(
        compute="_compute_origin_certificate_count", string='Integration Order Count')
    certificate_line_count = fields.Integer(
        compute="_compute_origin_certificate_line_count", string='Integration Order Count')
    irrevocable_contribution_id = fields.Many2one(
        string='Aporte Irrevocable', comodel_name='irrevocable.contribution')

    capital_reduction_id = fields.Many2one(
        string='Reducción de Capital', comodel_name='capital.reduction')

    # Integraciones
    integration_id = fields.Many2one('integration.order', store=False, readonly=True,
                                     states={'draft': [('readonly', False)]},
                                     string='Integration Order',
                                     help="Auto-complete from a past Integration order.")

    integration_order_count = fields.Integer(
        compute="_compute_origin_integration_count", string='Integration Order Count')

    # Costos de emisión de acciones
    account_share_cost_id = fields.Many2one('integration.order', store=False, readonly=True,
                                            states={
                                                'draft': [('readonly', False)]},
                                            string='Account Share Cost Order',
                                            help="Auto-complete from a past Account Share Cost order.")

    account_share_cost_count = fields.Integer(
        compute="_compute_origin_sc_count", string='Account Share Cost Order Count')

    @api.depends('line_ids.integration_line_id')
    def _compute_origin_integration_count(self):
        for move in self:
            move.integration_order_count = len(
                move.line_ids.integration_line_id.order_id)

    @api.depends('line_ids.account_share_cost_line_id')
    def _compute_origin_sc_count(self):
        for move in self:
            move.integration_order_count = len(
                move.line_ids.integration_line_id.order_id)

    @api.depends('line_ids.certificate_id')
    def _compute_origin_certificate_count(self):
        for move in self:
            move.integration_order_count = len(move.certificate_id)
    @api.depends('line_ids.certificate_line_id')
    def _compute_origin_certificate_line_count(self):
        for move in self:
            move.certificate_line_count = len(move.certificate_line_id)

    # ACTIONS

    def action_view_source_share_cost_orders(self):
        """Muestra los costos de emision asociados al asiento"""
        self.ensure_one()
        source_orders = self.line_ids.account_share_cost_line_id.order_id
        result = self.env['ir.actions.act_window']._for_xml_id(
            'higher_authority.action_ASC_form')
        if len(source_orders) > 1:
            result['domain'] = [('id', 'in', source_orders.ids)]
        elif len(source_orders) == 1:
            result['views'] = [
                (self.env.ref('higher_authority.account_share_cost_form', False).id, 'form')]
            result['res_id'] = source_orders.id
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    def action_view_source_integration_orders(self):
        """Muestra las integraciones asociadas al asiento"""
        self.ensure_one()
        source_orders = self.line_ids.certificate_line_id.order_id
        result = self.env['ir.actions.act_window']._for_xml_id(
            'higher_authority.action_IO_form')
        if len(source_orders) > 1:
            result['domain'] = [('id', 'in', source_orders.ids)]
        elif len(source_orders) == 1:
            result['views'] = [
                (self.env.ref('higher_authority.integration_order_form', False).id, 'form')]
            result['res_id'] = source_orders.id
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    def action_view_source_certificates_orders(self):
        """Muestra los bonos emitidos, asociados al asiento"""
        self.ensure_one()
        source_orders = self.line_ids.integration_line_id.order_id
        result = self.env['ir.actions.act_window']._for_xml_id(
            'higher_authority.action_CC_form')
        if len(source_orders) > 1:
            result['domain'] = [('id', 'in', source_orders.ids)]
        elif len(source_orders) == 1:
            result['views'] = [
                (self.env.ref('higher_authority.account_certificate_view_form', False).id, 'form')]
            result['res_id'] = source_orders.id
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    def action_view_source_certificates_lines(self):
        """Muestra los bonos emitidos (lineas), asociados al asiento"""
        self.ensure_one()
        source_orders = self.line_ids.certificate_line_id
        result = self.env['ir.actions.act_window']._for_xml_id(
            'higher_authority.action_certLine_form')
        if len(source_orders) > 1:
            result['domain'] = [('id', 'in', source_orders.ids)]
        elif len(source_orders) == 1:
            result['views'] = [
                (self.env.ref('higher_authority.account_certificate_line_view_form', False).id, 'form')]
            result['res_id'] = source_orders.id
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result