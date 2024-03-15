# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import frozendict


class WizardCreateVote(models.TransientModel):
    _name = 'wizard.create.vote'
    _description = 'Crear Votos'

    @api.onchange("assembly_meeting")
    def _onchange_all_topic_ids(self):
        meeting_topics=[]
        for wcv in self:
            if wcv.assembly_meeting:
                assembly_meeting=wcv.assembly_meeting
                for topic in assembly_meeting.assembly_meeting_line.topic:
                    meeting_topics.append(topic.id)
        # dominio
        res = {}
        res['domain'] = {'topic': [('id', '=', meeting_topics )], } 
        return res
    
    @api.onchange("assembly_meeting","topic")
    def _onchange_all_partner_ids(self):
        # habria que agregar un filtro mas para que aqullos accionistas que no asisitieron no puedan emitir votos
        partner_ids=[]
        for wcv in self:
            if wcv.assembly_meeting and wcv.topic:
                assembly_meeting=wcv.assembly_meeting
                topic=wcv.topic

                # filtro los accionsitas
                shareholders=wcv.env['res.partner'].search([]).filtered(
                    lambda p: p.shares.ids != []
                )
                # si el accinista esta registrado en la reunion y ademas no ha emitido votos por este topico, entonces puede votar
                for shldr in shareholders:
                    print(shldr)
                    if shldr in assembly_meeting.partner_ids:
                        votes=wcv.env['assembly.meeting.vote'].search([('partner_id','=',shldr.id),('topic','=',topic.id),('assembly_meeting','=',assembly_meeting.id)])
                        if not votes: 
                            partner_ids.append(shldr.id)

        # dominio
        res = {}
        res['domain'] = {'partner_id': [('id', '=', partner_ids )], } 
        return res
    
    assembly_meeting = fields.Many2one(
        string='Reunion Tratante', 
        comodel_name='assembly.meeting', readonly=False, domain=[('state','in',['draft','new','progress'])], required=True) # si creo el voto
    # a partir de una reunion, este campo se pasa por el contexto, si accedo al 
    
    topic=fields.Many2one(string='Asuntos', 
                          comodel_name='assembly.meeting.topic', 
                          readonly=False, 
                          store=True, onchange='_onchange_all_topic_ids', required=True)
    result=fields.Selection(string='Resultado', 
                            selection=[
        ('positive','Positivo'),
        ('negative','Negativo'),
        ('blank','Neutral'),
    ], required=True)
    partner_id = fields.Many2one(string='Accionista', 
                                 comodel_name='res.partner',
                                 readonly=False, onchange='_onchange_all_partner_ids', required=True) # hay que programar la logica para no elegir un accionista que ya haya
    # emitido los votos, es decir accionistas que aún no tenga ningun voto emitido en esta reunion, posiblemente un compute o onchange
    type=fields.Selection(string='Tipo', selection=[('normal','Normal'),('breaker','Desempate')], required=True)
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
                'date': fields.datetime.now(),
                'type':self.type,
            })
            # corroboro que los valores están asignados
            if '' in new_vote.values():
                raise UserError(_('Para emitir los votos, todos los campos deben ser completados'))
            self.env['assembly.meeting.vote'].create(new_vote)

    def _prepare_vote_values(self):
        self.ensure_one()
        vals={
            'name':'',
            'result':'',
            'topic':'',
            'partner_id':'',
            'assembly_meeting':'',
            'type':'',
        }
        return vals
    
    @api.model
    def default_get(self, fields_list):
        # OVERRIDE
        res = super().default_get(fields_list)

        if 'type' in fields_list and 'type' not in res:

            if self._context.get('active_model') in ['assembly.meeting','assembly.meeting.line']:
                res['type']=self._context.get('type')
                res['assembly_meeting']=self._context.get('meeting')
            else:
                raise UserError(_(
                    "Este wizard solo puede ser llamado desde una Reunion o Linea de Reunión"
                ))
        
            return res