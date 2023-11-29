# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


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


class AssemblyVote(models.Model):
    _name = 'assembly.meeting.vote'
    _description = 'Objeto Reunión de asamblea'
    _order = 'short_name desc'
    _rec_name = 'short_name'
    
    name = fields.Char(string='Título', 
                       required=True)
    short_name = fields.Char(string='Referencia', 
                             default='New',
                             required=True, 
                             copy=False, 
                             readonly=True)
    
    result=fields.Selection(string='Resultado', selection=[
        ('positive','Positivo'),
        ('negative','Negativo'),
        ('blank','Neutral'),
    ], readonly=True)

    # campos relacionales
    topic=fields.Many2one(string='Asuntos', 
                          comodel_name='assembly.meeting.topic', 
                          readonly=True)
    partner_id = fields.Many2one(string='Accionista', comodel_name='res.partner',readonly=True)
    assembly_meeting = fields.Many2one(
        string='Reunion Tratante', 
        comodel_name='assembly.meeting', readonly=True)
    # low level methods

    @api.model
    def create(self, vals):
        if vals.get('short_name', _('New')) == _('New'):
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'assembly.meeting.vote') or _('New')
        res = super().create(vals)
        return res

class AssemblyMeeting(models.Model):
    _inherit = 'assembly.meeting'

    assembly_vote=fields.One2many(string='Votos', 
                                  comodel_name='assembly.meeting.vote', 
                                  inverse_name='assembly_meeting',
                                  readonly=True)

class AssemblyMeetingTopic(models.Model):
    _inherit = 'assembly.meeting.topic'

    # campos relacionales
    assembly_vote=fields.One2many(string='Votos', 
                                    comodel_name='assembly.meeting.vote', 
                                    inverse_name='topic',
                                    readonly=True)