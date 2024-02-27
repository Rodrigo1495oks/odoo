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
                          comodel_name='assembly.meeting.topic',
                          change_default=True,
                          domain=[('state','=','new'),('meeting_assigned','=',False)],
                          store=True,
                          index=True)
    # domain=[('state','=','new'), ('meeting_assigned','=',False)],
    priority=fields.Selection(string='Prioridad', selection=[
        ('urgent','Urgente'),
        ('normal','Normal'),
        ('low','Baja')
    ], default='normal')
    assembly_meeting = fields.Many2one(
        string='Reunion Tratante', 
        comodel_name='assembly.meeting', index=True, required=True, ondelete='cascade')

    # onchanges
    @api.onchange("assembly_meeting.assembly_meet_type")
    def _onchange_all_topic_ids(self):
        res = {}
        if self.assembly_meeting.assembly_meet_type=='directory':
            res['domain'] = {'topic': [('topic_meet', '=',  'directory')], } 
        else:
            res['domain'] = {'topic': [('topic_meet', '=',  'assembly')], } 
        return res

    def action_approve_topic(self):
        for topic in self.topic:
            # COMO APRUEBO EL TOPICO?
            # SI HAY QUORUM?
            # SI HAY MAYORIA DE VOTOS?
            if topic.state == 'new' and self.assembly_meeting.state not in ['draft', 'finished', 'canceled']:
                quorum_per_type={
                    'ordinary': self.env.company.quorum_ord,
                    'extraordinary': self.env.company.quorum_ext,
                    'directory': self.env.company.quorum_ord,
                }
                if self.assembly_meeting.assembly_meet_type!='directory': 
                    shares=self.env['account.share'].search([])
                else:
                    shares=self.env['account.share'].search([('partner_id.position.type','=','director')])
                total_votes=sum([share.votes_num for share in shares])
                if total_votes<=0.0:
                    raise UserError('No hay acciones registradas')

                present_votes=0
                for partner in self.assembly_meeting.partner_ids:
                    for share in partner.shares:
                        present_votes+=share.votes_num
                # sum([share.votes_num for share in [partner.shares for partner in line.assembly_meeting.partner_ids]]) # probemos!!

                if (present_votes / total_votes) >= quorum_per_type[self.assembly_meeting.assembly_meet_type] and (topic.num_votes_plus/present_votes)>0.5:
                    topic._action_approve_topic()
                else:
                   raise UserError(_('El quorum no se completo o no recibio los votos suficientes'))
                
            else: 
                raise UserError(_('Ya fue rechazado o aprobado'))

    def action_refuse_topic(self):
        self.ensure_one()
        for topic in self.topic:
            # COMO APRUEBO EL TOPICO?
            # SI HAY QUORUM?
            # SI HAY MAYORIA DE VOTOS?
            if topic.state == 'new' and self.assembly_meeting.state not in ['draft', 'finished', 'canceled']:
                quorum_per_type={
                    'ordinary': self.env.company.quorum_ord,
                    'extraordinary': self.env.company.quorum_ext,
                    'directory': self.env.company.quorum_ord,
                }
                if self.assembly_meeting.assembly_meet_type!='directory': 
                    shares=self.env['account.share'].search([])
                else:
                    shares=self.env['account.share'].search([('partner_id.position.type','=','director')])
                total_votes=sum([share.votes_num for share in shares])
                if total_votes<=0.0:
                    raise UserError(_('No hay acciones registradas'))

                present_votes=0
                for partner in self.assembly_meeting.partner_ids:
                    for share in partner.shares:
                        present_votes+=share.votes_num

                if (present_votes / total_votes) >= quorum_per_type[self.assembly_meeting.assembly_meet_type] and (topic.num_votes_minus/present_votes)>0.5:
                    topic._action_refuse_topic()
                else:
                    raise UserError(_('El quorum no se completo o recibio votos de mayoria absoluta de acciones presentes con derecho a voto'))
            else: 
                raise UserError(_('Ya fue rechazado o aprobado'))
    def action_add_vote(self):
        """Accion auxiliar que tendra disponible el presidente del directorio
            para desempatar la votación
        """
        if self.user_has_groups('top_management.top_management_group_president'):
            for line in self:
                if line.topic.num_votes_plus==line.topic.num_votes_minus:
                    line.topic.num_votes_plus+=1
        else:
            return UserWarning('No se puede Desempatar')
            
class AssemblyMeetingTopic(models.Model):
    _inherit = 'assembly.meeting.topic'
    # campos relacionales
    assembly_meeting_line = fields.One2many(
        string='Orden del Día', 
        comodel_name='assembly.meeting.line', 
        inverse_name='topic', store=True, index=True)
    
class AssemblyMeeting(models.Model):
    _inherit = 'assembly.meeting'

    assembly_meeting_line = fields.One2many(
        string='Orden del Día', 
        comodel_name='assembly.meeting.line', 
        inverse_name='assembly_meeting', store=True, index=True)