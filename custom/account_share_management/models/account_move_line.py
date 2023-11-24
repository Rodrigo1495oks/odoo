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

        # Account Share Cost
    account_share_cost_line_id = fields.Many2one(
        'account.share.cost.line', 'Share Cost Line', ondelete='set null', index='btree_not_null')
    account_share_cost_order_id = fields.Many2one(
        'account.share.cost', 'Share Cost', related='account_share_cost_line_id.order_id', readonly=True)
    
    def _copy_data_extend_business_fields(self, values):
        # OVERRIDE to copy the 'purchase_line_id' field as well.
        super(AccountMoveLine, self)._copy_data_extend_business_fields(values)
        values['account_share_cost_line_id'] = self.account_share_cost_line_id.id