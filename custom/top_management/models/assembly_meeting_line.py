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
                          domain=[('state','=','new')],
                          store=True,
                          index=True)
    # domain=[('state','=','new'), ('meeting_assigned','=',False)],
    priority=fields.Selection(string='Prioridad', selection=[
        ('urgent','Urgente'),
        ('normal','Normal'),
        ('low','Baja')
    ], default='normal')
    state=fields.Selection(string='Estado',
                            selection=[('approved','Aprobado'),
                                        ('refused','Rechazado'),
                                        ('no_treating','Sin Tratar')], default='no_treating', readonly=True)
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
            if topic.state == 'new' and self.assembly_meeting.state=='count':
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
                
                if (present_votes / total_votes) >= quorum_per_type[self.assembly_meeting.assembly_meet_type]:
                    minus_votes=topic.env['assembly.meeting.vote'].search_count([('assembly_meeting','=',self.assembly_meeting.id),
                                                                                ('result','=','negative'),
                                                                                ('topic','=',topic.id)])
                
                    plus_votes=topic.env['assembly.meeting.vote'].search_count([('assembly_meeting','=',self.assembly_meeting.id),
                                                                                ('result','=','positive'),
                                                                                ('topic','=',topic.id)])
                    if plus_votes>minus_votes:
                        topic._action_approve_topic() 
                        self.state='approved'
                        message_id = self.env['message.wizard'].create({'message': _("El tema de Reunión fue:  \n <strong> ❤ Aprobado existosamente </strong>")})
                        return {
                                'name': _('Tema de Reunión Aprobado! 👍'),
                                'type': 'ir.actions.act_window',
                                'view_mode': 'form',
                                'res_model': 'message.wizard',
                                # pass the id
                                'res_id': message_id.id,
                                'target': 'new'
                                }
                    else: 
                        raise UserError('Este Tema, no ha reunido los votos suficientes para aprobarse')
                else:
                   raise UserError(_('El quorum no se completo'))
                
            else: 
                raise UserError(_('El asunto ya se trató o el cómputo aún no ha comenzado 😎'))

    def action_refuse_topic(self):
        self.ensure_one()
        for topic in self.topic:
            if topic.state == 'new' and self.assembly_meeting.state =='count':
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

                if (present_votes / total_votes) >= quorum_per_type[self.assembly_meeting.assembly_meet_type]:
                    minus_votes=topic.env['assembly.meeting.vote'].search_count([('assembly_meeting','=',self.assembly_meeting.id),
                                                                                ('result','=','negative'),
                                                                                ('topic','=',topic.id)])
                
                    plus_votes=topic.env['assembly.meeting.vote'].search_count([('assembly_meeting','=',self.assembly_meeting.id),
                                                                                ('result','=','positive'),
                                                                                ('topic','=',topic.id)])

                    if minus_votes>plus_votes:
                        topic._action_refuse_topic() 
                        self.state='refused'
                        message_id = self.env['message.wizard'].create({'message': _("El tema de Reunión fue:  \n <strong>Rechazado existosamente 🤷‍♀️</strong>")})
                        return {
                                'name': _('Tema de Reunión Rechazado! ❌'),
                                'type': 'ir.actions.act_window',
                                'view_mode': 'form',
                                'res_model': 'message.wizard',
                                # pass the id
                                'res_id': message_id.id,
                                'target': 'new'
                                }
                    else: 
                        raise UserError('Este Tema, no ha reunido los votos suficientes para rechazarse')
                else:
                   raise UserError(_('El quorum no se completo o no recibio los votos suficientes'))
            else: 
                raise UserError(_('El asunto ya se trató o el cómputo aún no ha comenzado 😎'))
            
    def action_add_vote(self):
        """Accion auxiliar que tendra disponible el presidente del directorio
            para desempatar la votación
        """
        if self.user_has_groups('top_management.top_management_group_president') and self.topic.state == 'new' and self.assembly_meeting.state =='count':
            for line in self:
                if line.topic.state == 'new':
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

                if (present_votes / total_votes) >= quorum_per_type[self.assembly_meeting.assembly_meet_type] :
                    vote=line.env['assembly.meeting.vote'].search_count([('type','=','breaker'),('assembly_meeting','=',line.   assembly_meeting.id), ('topic','=',line.topic.id)],limit=1)
                    
                    if not vote:
                        minus_votes=line.topic.env['assembly.meeting.vote'].search_count([('assembly_meeting','=',self.assembly_meeting.id),
                                                                                ('result','=','negative'),
                                                                                ('topic','=',line.topic.id)])
                        plus_votes=line.topic.env['assembly.meeting.vote'].search_count([('assembly_meeting','=',self.assembly_meeting.id),
                                                                                ('result','=','positive'),
                                                                                ('topic','=',line.topic.id)])
                        if minus_votes==plus_votes:
                            # line.action_register_vote() Creo el voto manualmente dado que no funciona el wizard aqui
                            vote_vals={
                                    'name':'Voto (%s) - Reunión (%s) - Asunto (%s)'%('Positivo', self.assembly_meeting.short_name, self.topic.short_name),
                                    'result':'positive',
                                    'topic':self.topic.id,
                                    'partner_id':self.env.user.partner_id.id,
                                    'assembly_meeting':self.assembly_meeting.id,
                                    'date': fields.datetime.now(),
                                    'type':'breaker',
                                        }
                            self.env['assembly.meeting.vote'].create(vote_vals)

                            message_id = self.env['message.wizard'].create({'message': _("El voto de desempate fue exitosamente \n <strong>registrado</strong>")})
                            return {
                                'name': _('Muy Bien!'),
                                'type': 'ir.actions.act_window',
                                'view_mode': 'form',
                                'res_model': 'message.wizard',
                                # pass the id
                                'res_id': message_id.id,
                                'target': 'new'
                                }
                    else:
                        raise UserError('Ya existe un voto de Desempate en esta reunión 😁')
        else:
            raise UserError('No se puede Desempatar, no tiene los permisos necesarios')
        
    def action_register_vote(self):
        ''' Open the account.payment.register wizard to pay the selected journal entries.
        :return: An action opening the account.payment.register wizard.
        '''
        return {
            'name': _('Registrar Voto Desempate'),
            'res_model': 'wizard.create.vote',
            'view_mode': 'form',
            'context': {
                'active_model': 'assembly.meeting.line',
                'active_ids': self.ids,
                'meeting':self.assembly_meeting.id,
                'type':'breaker',
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }
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