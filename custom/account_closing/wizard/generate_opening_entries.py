# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import frozendict


class CreateOpeningEntries(models.TransientModel):
    _name = 'create.opening.entry'
    _description = 'Generar Asientos de cierre'

    