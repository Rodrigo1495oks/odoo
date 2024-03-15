# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import frozendict


class MessageWizard(models.TransientModel):
    _name = 'message.wizard'

    message = fields.Text('Message', required=True)

    # @api.model
    def action_ok(self):
        """ close wizard"""
        return {'type': 'ir.actions.act_window_close'}