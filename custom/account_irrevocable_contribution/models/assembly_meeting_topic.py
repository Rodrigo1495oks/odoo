# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo import models, fields, api, tools
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError, ValidationError


class AssemblyMeetingTopic(models.Model):
    _name = 'assembly.meeting.topic'
    _inherit = 'assembly.meeting.topic'
    
    def action_load_issuance(self):
        ''' Open the account.issuance.register wizard to pay the selected journal entries.
        :return: An action opening the account.issuance.register.
        '''
        return {
            'name': _('Register Share Issuance'),
            'res_model': 'wizard.issuance.register',
            'view_mode': 'form',
            'context': {
                'active_model': 'assembly.meeting.topic',
                'active_ids': self.ids,
                'topic':self.id,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }