# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from bisect import bisect_left
from collections import defaultdict


class AccountJournal(models.Model):
    _inherit = "account.journal"


    type=fields.Selection(selection_add=[
        ('suscription','Suscription'),
    ], ondelete = {
        'suscription': lambda recs: recs.write({'move_type': 'entry'}),
    })
