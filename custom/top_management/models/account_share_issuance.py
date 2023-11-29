# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo import models, fields, api, tools
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError, ValidationError


class SharesIssuance(models.Model):
    _inherit = 'account.share.issuance'

    topic = fields.Many2one(string='Tema de Reunión',       
                             comodel_name='assembly.meeting.topic',
                             ondelete='restrict', readonly=True)