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


class ReductionList(models.Model):
    _name = 'capital.reduction.list'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Reducciones por Cancelación'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'

    short_name = fields.Char(string='Referencia', default='New',
                             required=True, copy=False, readonly=True)

    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('approved', 'Aprobado'),
        ('confirm', 'Confirmado'),
        ('cancel', 'Cancelado')
    ], default='draft', readonly=True)

    topic = fields.Many2one(
        string='Tópico', comodel_name='assembly.meeting.topic', readonly=True)

    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company.id, readonly=True)
    percentage_to_reduce = fields.Float(
        string='Porcentaje de Reducción', default=0.0, help='Porcentaje a reducir para mantener el VPP')
    reduction_ids = fields.One2many(
        string='Reducciones', comodel_name='capital.reduction', inverse_name='')
    user_id = fields.Many2one('res.users', string='Usuario',
                              index=True, tracking=True, default=lambda self: self.env.user, help='El usuario que Crea la Orden')
    notes = fields.Html(string='Notas')

    # METHODS

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
                raise UserError('No puede cancelarse la Reducción')

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
                """Itero sobre todos los accionistas"""

                partners_list = self.env['res.partner'].search(
                    ['shares', '=', True])

                for partner in partners_list:
                    Reduction = self.env['capital.reduction']
                    NewReduction = self.env['capital.reduction']
                    vals_for_reduction = self._prepare_reduction_values()
                    vals_for_reduction['partner_id'] = partner
                    redMove = NewReduction.create(vals_for_reduction)
                    self.reduction_ids.append(0, 0, redMove)
                Reduction |= redMove
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

    # Lógica (Helpers)
    def _prepare_topic_values(self):
        self.ensure_one()
        topic_values = {
            "name": "Reducción de Capital. \n",
            "description": "Reducción de Capital por Cancelación",
            "state": "draft",
            "topic_type": "reduction",
        }
        return topic_values

    def _prepare_reduction_values(self):
        self.ensure_one()
        reduction_values = {
            'name': f'Reducción desde - {self.short_name}',
            'date': fields.Date.today(),
            'date_due': fields.Date.today() + relativedelta(days=90),
            'state': 'approved',
            'reduction_type': 'cancelation',
            'notes': 'Creada Desde una Orden de Cancelación, Aprobada por el Gerente de Finanzas',
            'partner_id': '',
            'topic': self.topic
        }
        return reduction_values

    # LOW LEVEL METHODS
    @api.model
    def create(self, vals):
        # Compruebo que no haya otra cancelación de acciones abierta
        for cancelation in self.ids:
            if cancelation.state in ['draft', 'new', 'approved']:
                raise UserError(
                    'No se puede crear nuevas cancelaciones si hay otras pendientes')

        if vals.get('short_name', _('New')) == _('New'):
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'capital.reduction.list') or _('New')
        res = super(ReductionList, self.create(vals))
        return res

        # CONSTRAINS

    @api.constrains('percentage_to_reduce')
    def _check_percentage(self):
        for record in self:
            if record.percentage_to_reduce > 1.0:
                raise ValidationError(
                    'El porcentaje a reducir no puede ser superior al 100%')
