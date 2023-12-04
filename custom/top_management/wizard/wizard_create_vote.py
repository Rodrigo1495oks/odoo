# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import frozendict


class WizardCreateVote(models.TransientModel):
    _name = 'wizard.create.vote'
    _description = 'Crear Votos'

    @api.depends('assembly_meeting')
    def _compute_topics_availables(self):
        """Si para este asunto, de esta reunion, el accionista seleccinado, ya
            ha emitido un voto, entonces desabilito el topico, ya no lo muestro en la lista desplegable.
        """
        topics=[]
        if self.assembly_meeting:
             for topic in self.env['assembly.meeting.topic'].search([('state','in',['draft','new']),('assembly_meeting_line.assembly_meeting','=','assembly_meeting')]):
                 if topic.assembly_vote:
                    available=True
                    for vote in topic.assembly_vote:
                        if vote.partner_id ==self.partner_id:
                            available=False
                            break
                        if available:
                            topics.append(topic)
        self.topic= topics
                            
    partner_id = fields.Many2one(string='Accionista', comodel_name='res.partner',readonly=False)
    assembly_meeting = fields.Many2one(
        string='Reunion Tratante', 
        comodel_name='assembly.meeting', readonly=False, domain=[('state','in',['draft','new'])])
    
    topic=fields.Many2one(string='Asuntos', 
                          comodel_name='assembly.meeting.topic', 
                          readonly=False, 
                          store=True,
                          compute='_compute_topics_availables')
    result=fields.Selection(string='Resultado', 
                            selection=[
        ('positive','Positivo'),
        ('negative','Negativo'),
        ('blank','Neutral'),
    ])

    
    # Actions
    def create_name(self):
        self.ensure_one()
        return 'Voto (%s) - Reunión (%s) - Asunto (%s)'%(self.result, self.assembly_meeting.short_name, self.topic.short_name)

    def action_create_votes(self):
        """Crea un voto por cada derecho a voto de las acciones del accionista"""
        votes=0 # votos totales

        for share in self.partner_id.shares:
            votes+=share.votes_num
                
        for i in range(0,votes):
            new_vote=self._prepare_vote_values()
            new_vote.update({
                'name':self.create_name(),
                'result':self.result,
                'topic':self.topic.id,
                'partner_id':self.partner_id.id,
                'assembly_meeting':self.assembly_meeting.id,
            })
            self.env['assembly.meeting.vote'].create(new_vote)

    def _prepare_vote_values(self):
        self.ensure_one()
        vals={
            'name':'',
            'result':'',
            'topic':'',
            'partner_id':'',
            'assembly_meeting':'',
        }
        return vals