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


class AssemblyMeeting(models.Model):
    _name = 'assembly.meeting'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _inherits = {'calendar.event': 'event_id'}
    _description = 'Objeto Reunión de asamblea'
    # _order = 'short_name desc'
    # _rec_name = 'short_name'
    event_id = fields.Many2one(comodel_name='assembly.meeting',
                               required=True, ondelete='cascade', readonly=True, index=True, store=True)

    # campos que voy a definir para este modelo en particular
    short_name = fields.Char(string='Referencia', default='New',
                             required=True, copy=False, readonly=True)
    assembly_meet_type = fields.Selection(string='Tipo de Asamblea', selection=[
        ('ordinary', 'Asamblea Ordinaria'),
        ('extraordinary', 'Asamblea Extraordinaria')
    ])
    partner_ids = fields.Many2many(string='Accionistas Presentes', comodel_name='res.partner',
                                   column1='assembly_meet', column2='shareholder', relation='assembly_meeting_shareholders')

    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('finished', 'Finalizada'),
        ('canceled', 'Cancelada')
    ])

    topics = fields.One2many(string='Temas a Tratar', comodel_name='assembly.meeting.topic',
                             inverse_name='assembly_meeting', store=True, index=True, domain="[('state','in','new'),('meeting_assigned','=','False')]")

    # computos copiados del modelo calenbdar.event (recordar que los modelos delegados no heredan los metodos, solo los campos)

    def action_draft(self):
        for meet in self:
            if meet.state not in ['canceled', 'finished']:
                meet.state = 'draft'

    def action_confirm(self):
        for meet in self:
            meet.state = 'new' if meet.state in ['draft'] else None

    def action_finish(self):
        for meet in self:
            meet.state = 'finished' if meet.state in ['new'] else None
    # low level methods

    @api.model
    def create(self, vals):
        if vals.get('short_name', _('New')) == _('New'):
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'assembly.meeting') or _('New')
        res = super(AssemblyMeeting, self.create(vals))
        return res


class AssemblyMeetingTopic(models.Model):
    _name = 'assembly.meeting.topic'
    # _inherits = {'account.asset', 'ref_name'}
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Objeto Temas de reunion'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'

    # campos computados
    @api.depends('assembly_meeting')
    def _compute_meeting_assigned(self):
        for record in self:
            if len(record.assembly_meeting) > 0:
                record.meeting_assigned = True
                return True

    short_name = fields.Char(
        string='Referencia', required=True, index='trigram', copy=False, default='New')

    name = fields.Char(string='Título')
    description = fields.Text(
        string='Descripción del tema a tratar', ondelete='restrict')
    meeting_assigned = fields.Boolean(
        string='Reunión Asignada', default=False, readonly=True, compute='_compute_meeting_assigned')
    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('approved', 'Aprobado'),
        ('refused', 'Rechazado'),
        ('cancel', 'Cancelado')
    ], default='draft', required=True, readonly=True)
    topic_type = fields.Selection(string='Tipo de Asunto', selection=[
        ('issuance', 'Emisión de Acciones'),
        ('irrevocable', 'Aporte Irrevocable'),
        ('reduction', 'Cancelar Acciones'),
        ('redemption', 'Acciones en Cartera'),
        ('share_sale', 'Venta de Acciones')

    ], required=True)
    # campos relacionales
    assembly_meeting = fields.Many2one(
        string='Reunion Tratante', comodel_name='assembly.meeting')
    # secuencia numerica
    # emision de acciones

    share_issuance = fields.One2many(
        string='Orden de Emisión', readonly=True, index=True, store=True, comodel_name='shares.issuance', inverse_name='topic')

    reduction_cancelation = fields.One2many(string='Cancelación de Acciones', readonly=True,
                                            index=True, store=True, comodel_name='capital.reduction.list', inverse_name='topic')

    def action_confirm(self):
        for topic in self:
            if topic.state not in ['new'] and topic.assembly_meeting.state not in ['draft', 'finished', 'canceled']:
                topic.state = 'new'
            else:
                raise UserError('topico ya tratado o reunion no establecida')

    def name_get(self):
        result = []
        for topic in self:
            share_issuances = topic.share_issuance.mapped('short_name')
            name = '%s (%s)' % (topic.short_name, ', '.join(share_issuances))
            result.append((topic.id, name))
            return result

    def action_approve_topic(self):
        for topic in self:
            if topic.state == 'new' and topic.assembly_meeting.state not in ['draft', 'finished', 'canceled']:
                topic.state = 'aproved'
            else:
                raise UserError('No puede aprobarse este tópico')

    def action_refuse_topic(self):
        for topic in self:
            if topic.state not in ['draft', 'aproved', 'refused'] and topic.assembly_meeting.state not in ['draft', 'finished', 'canceled']:
                topic.state = 'refused'
            else:
                raise UserError('No puede rechazarse este tópico')

    def action_draft(self):
        for meet in self:
            if meet.state in ['new']:
                meet.state = 'draft'

    def action_set_canceled(self):
        self.ensure_one()
        for topic in self:
            if topic.state in ['new']:
                topic.state = 'cancel'
            else:
                raise UserError(
                    'No puede Cancelarse un inmueble que ya esta cancelado o vendido')

    @api.model
    def create(self, vals):
        if vals.get('short_name', _('New')) == _('New'):
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'assembly.meeting.topic') or _('New')
        res = super(AssemblyMeeting, self.create(vals))
        return res