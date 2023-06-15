import ast
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta
from functools import lru_cache

from odoo import api, fields, models, Command, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import frozendict, formatLang, format_date, float_compare, Query
from odoo.tools.sql import create_index
from odoo.addons.web.controllers.utils import clean_action

from odoo.addons.account.models.account_move import MAX_HASH_VERSION


class AccountMoveLine(models.Model):
    # _name = "account.move.line"
    _inherit = "account.move.line"

    share_cost_line_id = fields.Many2one(
        string='Costo Orden de Emision', comodel_name='account.share.cost.line', index=True)
    
    
