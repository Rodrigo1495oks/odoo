# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, timedelta
from odoo import models, fields, api, tools
from odoo.exceptions import ValidationError
from odoo.addons.base.models.res_partner import _tz_get
from odoo.tools.translate import _
from odoo.tools.misc import get_lang
from odoo.tools import pycompat
from odoo.exceptions import UserError, AccessError

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
            if record.assembly_meeting:
                record.meeting_assigned = True
            else:
                record.meeting_assigned = False

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
        ('share_sale', 'Venta de Acciones'),
    ], required=True)

    # secuencia numerica
    # emision de acciones
    share_issuance=fields.One2many(string='Emisión de Acciónes', comodel_name='account.share.issuance', readonly=True, inverse_name='topic')

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
                    'No puede Cancelarse un tópico que ya esta cancelado o aprobado')

    @api.model
    def create(self, vals):
        if vals.get('short_name', _('New')) == _('New'):
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'assembly.meeting.topic') or _('New')
        return super().create(vals)