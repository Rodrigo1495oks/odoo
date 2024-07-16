# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import frozendict


class WizardShowPendings(models.TransientModel):
    _name = 'wizard.show.pendings'
    _description = 'Shows outstanding balances of shareholders'

    irr_cont_id = fields.Many2one(string='Contribution',
                                  comodel_name='account.irrevocable.contribution',
                                  readonly=True)
    cash_lines_pending = fields.One2many(string='Cash Lines',
                                         comodel_name='account.suscription.cash.line',
                                         inverse_name='wizard_show_pending',
                                         readonly=True)
    credit_pending = fields.Boolean(string='Credit Pending', readonly=True, help='')
    qty_pending = fields.Integer(string='Qty Pending', default=0)


    @api.model
    def default_get(self, fields_list):
        # OVERRIDE
        res = super().default_get(fields_list)
        if 'irr_cont_id' in fields_list and 'irr_cont_id' not in res:
            if self._context.get('active_model') in ['account.irrevocable.contribution']:
                res['irr_cont_id'] = self._context.get('irr_cont_id')
                res['cash_lines_pending'] = self._context.get('lines_amount_pending')
                res['credit_pending'] = self._context.get('credit_pending')
                res['product_pending'] = self._context.get('product_pending')
            else:
                raise UserError(_(
                    "This wizard can only be called from a Meeting Subject"
                ))
            return res
