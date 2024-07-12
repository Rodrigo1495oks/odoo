# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import frozendict

class WizardCreateVote(models.TransientModel):
    _name = 'wizard.create.vote'
    _description = 'Crear Votos'

    def action_create_votes(self):
        """Crea un voto por cada derecho a voto de las acciones del accionista"""
        # Reviso si el accionista posee alguna orden vencida

        if self.env['account.suscription.order'].search_count(domain=[('partner_id','=',self.partner_id.id),('date_due','<',fields.Date.today()),('state','=','suscribed')], limit=1)>0:
            raise UserWarning("Advertencia: el Accionista posee Órdenes de Integración Vencidas. Por Favor Regularice su situación. Hasta tanto, quedan suspendidos el derecho a voto")
        return super(WizardCreateVote, self).action_create_votes()