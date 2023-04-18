# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import collections
import hashlib
import re
import pytz
import requests
from odoo.exceptions import UserError
from werkzeug import urls

from datetime import datetime, timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api, tools

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
from odoo.tools.misc import get_lang
from odoo.tools import pycompat
from odoo.exceptions import UserError, AccessError


class SharesIssuance(models.Model):
    _name = 'shares.issuance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # _inherits = {'calendar.event': 'event_id'}
    _description = 'Objeto Reunión de asamblea'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'

    def _compute_currency_rate(self):
        for share in self:
            share.currency_rate = self.env['res.currency']._get_conversion_rate(
                share.company_id.currency_id, share.currency_id, share.company_id, share.date_share)

    @api.depends('nominal_value', 'price')
    # busca en el modelo relacionado e l campo precio total
    def _compute_price(self):
        # calcula la prima o el desuento de emision en caso de corresponder
        # presupuesto/pedido de compra
        currency = self.currency_id or self.shareholder.property_sharehold_currency_id or self.env.company.currency_id
        for issuance in self:
            nom_price = issuance.nominal_value
            price = issuance.price
            if nom_price > price:
                issuance.update({  # actualizo loscampos de este modelo
                    'issue_discount': currency.round(nom_price-price),
                    'issue_premium': 0
                })
            if nom_price < price:
                issuance.update({  # actualizo loscampos de este modelo
                    'issue_discount': 0,
                    'issue_premium': currency.round(price-nom_price)
                })

    short_name = fields.Char(string='Referencia')

    name = fields.Char(string='Nombre')

    makeup_date = fields.Datetime(string='Fecha de Confección', readonly=True,
                                  help='Fecha en que se ha creado esta orden, a partir del topico aprobado correspondiente')
    date_of_issue = fields.Datetime(
        string='Fecha de Emisión', help='Fecha en que se ha ejecutado esta orden y creado las acciones')
    # campos relacionales

    # campos para crear las acciones

    share_type = fields.Many2one(
        string='Grupo de acciones', comodel_name='account.share.type', ondelete='restrict')

    votes_num = fields.Integer(string='Número de Votos',
                               related='share_type.number_of_votes', store=True)  # puede modificarse en la accion mientras sea "editable"

    shareholder = fields.Many2one(
        string='Accionista', comodel_name='account.shareholder', store=True, index=True)

    # valores y cotizacion
    shares_qty = fields.Integer(
        string='Cantidad', default=0, required=True, help='Cantidad de acciones a emitir')

    nominal_value = fields.Float(
        string='Valor de Emisión', required=True, copy=True)

    price = fields.Float(string='Valor de mercado',
                         help='El el valor al cual se vendió la accion, el monto total que pago el accionista por adquirir la acción', readonly=True, copy=True, compute='_compute_price')

    issue_premium = fields.Float(
        string='Prima de emision', help='Cotizacion sobre la par', compute='_compute_price')

    issue_discount = fields.Float(
        string='Descuento de Emisión', help='Descuento bajo la par', compute='_compute_price')

    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company.id, readonly=True)
    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('approved', 'Aprobado'),
        ('suscribed', 'Suscrito')
        ('cancel', 'Cancelado')
    ], default='draft')

    shareholder = fields.Many2one(
        string='Accionista', comodel_name='account.shareholder')
    share_type = fields.Many2one(
        string='Grupo de acciones', comodel_name='account.share.type', ondelete='restrict')
    shares = fields.One2many(string='Acciones a emitir', help='Acciones creadas',
                             comodel_name='account.share', inverse_name='share_issuance', index=True)
    suscription_order = fields.Many2one(
        string='Suscripción', help='Suscripcion de acciones creada', comodel_name='suscription.order', index=True)
    share_cost = fields.One2many(
        string='Costos de Emisión', comodel_name='account.share.cost', inverse_name='share_issuance', readonly=True)
    topic = fields.Many2one(string='Tema de Reunión',
                            comodel_name='assembly.meeting.topic', ondelete='restrict')

    irrevocable_contribution = fields.Many2one(
        string='Aporte Irrevocable', comodel_name='irrevocable.contribution', index=True, copy=True, readonly=True)

    def action_approve(self):
        for issuance in self:
            if issuance.state not in ['draft', 'cancel', 'suscribed', 'approved'] and issuance.topic.id.state == 'approved':
                issuance.state = 'approved'
                # creo las acciones
                for i in self.shares_qty:
                    share_vals = issuance._prepare_share_values()
                    self.env['account.share'].create(share_vals)
            else:
                raise UserError('Orden de emision no autorizada')

    def action_cancel(self):
        for issuance in self:
            if issuance.state not in ['draft', 'new', 'suscribed'] and issuance.topic.id.state == 'refused':
                issuance.state = 'cancel'
                for share in issuance.shares:
                    share.share_cancel()

    def action_suscribe(self):
        for issuance in self:
            if issuance.state == 'approved':
                for share in issuance.shares:
                    share.share_aprove()
            else:
                raise UserError('Acción no válida')

    # methods

    def _prepare_share_values(self):
        res = {
            'state': 'draft',
            'date_of_issue': self.date_of_issue,
            'share_type': self.share_type.id,
            'votes_num': self.votes_num,
            'shareholder': self.shareholder.id,
            'nominal_value': self.nominal_value,
            'price': self.price,
            'issue_premium': self.issue_premium,
            'issue_discount': self.issue_discount,
            'share_issuance': self.id,
            'suscription_order': self.suscription_order.id,
        }
        return res