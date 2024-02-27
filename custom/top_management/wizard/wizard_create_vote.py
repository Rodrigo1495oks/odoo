# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import frozendict


class WizardCreateVote(models.TransientModel):
    _name = 'wizard.create.vote'
    _description = 'Crear Votos'

                            
    assembly_meeting = fields.Many2one(
        string='Reunion Tratante', 
        comodel_name='assembly.meeting', readonly=False, domain=[('state','in',['draft','new'])]) # si creo el voto
    # a partir de una reunion, este campo se pasa por el contexto, si accedo al 
    
    topic=fields.Many2one(string='Asuntos', 
                          comodel_name='assembly.meeting.topic', 
                          readonly=False, 
                          store=True,
                            domain=[('state','in',['draft','new']),('assembly_meeting_line.assembly_meeting','=','assembly_meeting')])
    result=fields.Selection(string='Resultado', 
                            selection=[
        ('positive','Positivo'),
        ('negative','Negativo'),
        ('blank','Neutral'),
    ])
    partner_id = fields.Many2one(string='Accionista', 
                                 comodel_name='res.partner',
                                 readonly=False, domain=[('')])

    
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