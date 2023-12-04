# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo.exceptions import UserError
from werkzeug import urls

from datetime import datetime, timedelta


from odoo import models, fields, api, tools


from odoo.exceptions import ValidationError
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tools.translate import _
from odoo.tools.misc import get_lang
from odoo.tools import pycompat
from odoo.exceptions import UserError, AccessError


class AssemblyMeetingLine(models.Model):
    _name = 'assembly.meeting.line'
    # _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Objeto Línea tópico Reunión de asamblea'
    # _order = 'short_name desc'
    # _rec_name = 'short_name'
    name=fields.Char(string='Descripcion')
    topic=fields.Many2one(string='Asunto', 
                          comodel_name='assembly.meeting.topic', domain="[('state','in','new')]")
    priority=fields.Selection(string='Prioridad', selection=[
        ('urgent','Urgente'),
        ('normal','Normal'),
        ('low','Baja')
    ], default='normal')

    assembly_meeting = fields.Many2one(
        string='Reunion Tratante', 
        comodel_name='assembly.meeting')

    def action_approve_topic(self):
        for line in self:
            # COMO APRUEBO EL TOPICO?
            # SI HAY QUORUM?
            # SI HAY MAYORIA DE VOTOS?
            if line.topic.state == 'new' and line.assembly_meeting.state not in ['draft', 'finished', 'canceled']:
                quorum_per_type={
                    'ordinary': self.env.company.quorum_ord,
                    'extraordinary': self.env.company.quorum_ext,
                }
                shares=self.env['account.share'].search()
                total_votes=sum([share.votes_num for share in shares])
                if total_votes<0.0:
                    raise UserError('No hay acciones registradas')

                present_votes=sum([share.votes_num for share in [partner.shares for partner in line.assembly_meeting.partner_ids]]) # probemos!!

                if (present_votes / total_votes) >= quorum_per_type[self.assembly_meeting.assembly_meet_type] and (line.topic.num_votes_plus/present_votes)>0.5:
                    line.topic._action_approve_topic()
                else:
                    raise UserWarning('El quorum no se completo o no recibio los votos suficientes')
            else: 
                raise UserWarning('Ya fue rechazado o aprobado')

    def action_refuse_topic(self):
        for line in self:
            # COMO APRUEBO EL TOPICO?
            # SI HAY QUORUM?
            # SI HAY MAYORIA DE VOTOS?
            if line.topic.state == 'new' and line.assembly_meeting.state not in ['draft', 'finished', 'canceled']:
                quorum_per_type={
                    'ordinary': self.env.company.quorum_ord,
                    'extraordinary': self.env.company.quorum_ext,
                }
                shares=self.env['account.share'].search()
                total_votes=sum([share.votes_num for share in shares])
                if total_votes<0.0:
                    raise UserError('No hay acciones registradas')

                present_votes=sum([share.votes_num for share in [partner.shares for partner in line.assembly_meeting.partner_ids]]) # probemos!!

                if (present_votes / total_votes) >= quorum_per_type[self.assembly_meeting.assembly_meet_type] and not (line.topic.num_votes_plus/present_votes)>0.5:
                    line.topic._action_refuse_topic()
                else:
                    raise UserWarning('El quorum no se completo o recibio votos de mayoria absoluta de acciones presentes con derecho a voto')
            else: 
                raise UserWarning('Ya fue rechazado o aprobado')
            
            
class AssemblyMeetingTopic(models.Model):
    _inherit = 'assembly.meeting.topic'
    # campos relacionales
    assembly_meeting_line = fields.One2many(
        string='Orden del Día', 
        comodel_name='assembly.meeting.line', 
        inverse_name='topic')
    
class AssemblyMeeting(models.Model):
    _inherit = 'assembly.meeting'

    assembly_meeting_line = fields.One2many(
        string='Orden del Día', 
        comodel_name='assembly.meeting.line', 
        inverse_name='assembly_meeting')