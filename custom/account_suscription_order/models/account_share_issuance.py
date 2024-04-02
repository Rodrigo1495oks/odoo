# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo import models, fields, api, tools
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError, ValidationError


class SharesIssuance(models.Model):
    _name = 'account.share.issuance'
    _inherit = 'account.share.issuance'
    
    def action_approve(self):
        res =super().action_approve()
        for issuance in self:
            if issuance.state not in ['draft', 'cancel', 'suscribed', 'approved'] and self.user_has_groups('account_financial_policies.account_financial_policies_group_manager') and issuance.topic.state == 'approved':
                issuance.state = 'approved'
                # creo las acciones
                for i in range(self.shares_qty):
                    share_vals = issuance._prepare_share_values()
                    self.env['account.share'].create(share_vals)
                
            else:
                raise UserError(_('Orden de emision no autorizada'))
        return res
    
    def action_confirm(self):
        res=super().action_confirm()
        for issue in self:
            if issue.state == 'draft' and self.user_has_groups('account_financial_policies.account_financial_policies_stock_market_group_manager'):
                topic_vals=issue._prepare_topic_values()
                topic_vals['share_issuance'].append((6,0,issue.id))
                # ValueError: dictionary update sequence element #0 has length 1; 2 is required Python Dictionary
                newTopic=issue.env['assembly.meeting.topic'].create(topic_vals)
                issue.state='new'
        return res
    
    def action_suscribe(self):
        res=super().action_suscribe()
        for issuance in self:
            if issuance.state == 'approved' and issuance.topic.state:
                if issuance.topic.state=="approved":
                    issuance.state == 'suscribed'
                    for share in issuance.shares:
                        share.share_aprove()
            else:
                for share in issuance.shares:
                    share.state='new'
        return res
    

    # Action helpers
    def _prepare_topic_values(self):
        self.ensure_one()
        vals = {
            "name": " Emisión N°: %s /= %s"%(self.short_name, self.makeup_date),
            'state': 'draft',
            "description": 'Emisión de acciones',
            "topic_type": "issuance",
            'topic_meet':'assembly',
            "share_issuance": []
        }
        return vals