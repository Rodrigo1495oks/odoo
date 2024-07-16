# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo import models, fields, api, tools
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError, ValidationError


class SharesIssuance(models.Model):
    _name = 'account.share.issuance'
    _inherit = 'account.share.issuance'

    contribution_id=fields.One2many(string='Contribution Order',
                                    comodel_name='account.irrevocable.contribution',
                                    inverse_name='share_issuance_id'
                                    ,readonly=True, help='Related Contribution Order')

