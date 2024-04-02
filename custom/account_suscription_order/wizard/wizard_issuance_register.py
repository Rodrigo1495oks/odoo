# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import frozendict


class WizardCreateVote(models.TransientModel):
    _name = 'wizard.issuance.register'
    _description = 'Crear Votos'
