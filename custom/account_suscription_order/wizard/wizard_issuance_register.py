# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import frozendict


class WizardCreateVote(models.TransientModel):
    _name = 'wizard.issuance.register'
    _description = 'Associate Issuance of shares with issues'

    topic = fields.Many2one(string='Tema de Reunión',       
                             comodel_name='assembly.meeting.topic',
                             ondelete='restrict', readonly=True)
    share_issuance_ids=fields.Many2many(string='Issuance of Shares',column1='wizard_issuance_register',column2='share_issuance',comodel_name='account.share.issuance', readonly=False, inverse_name='topic',domain=[
        ('state','=','new'),('topic','=',False)
    ])

    # Creo la funcion para asignar las ordenes a este tópico
    def assign_issue_ids(self):
        self.ensure_one()
        if len(self.share_issuance_ids)>0:
            this_topic=self.env['account.share.issuance'].browse(self.topic.id)
            
            print('.....................', this_topic.fields_get())
            if this_topic.exists():
                for issuance in self.share_issuance_ids:
                    this_topic.write({
                        "share_issuance": (4,issuance.id)
                    })
        else:
            message_id = self.env['message.wizard'].create({'message': _("Error: Please Assign Issue Orders First!")})
            return {
                    'name': _('Assign issue orders first! 😙'),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'res_model': 'message.wizard',
                    # pass the id
                    'res_id': message_id.id,
                    'target': 'new'
                    }
    @api.model
    def default_get(self, fields_list):
        # OVERRIDE
        res = super().default_get(fields_list)
        if 'topic' in fields_list and 'topic' not in res:

            if self._context.get('active_model') in ['assembly.meeting.topic']:
                res['topic']=self._context.get('topic')
            else:
                raise UserError(_(
                    "This wizard can only be called from a Meeting Subject"
                ))
            return res