# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from collections import defaultdict
from datetime import timedelta
from operator import itemgetter

from odoo import _, api, Command, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.tools.misc import clean_context, OrderedSet, groupby

PROCUREMENT_PRIORITIES = [('0', 'Normal'), ('1', 'Urgent')]


class StockMove(models.Model):
    _inherit = "stock.move"

    share_cost_line_id = fields.Many2one(
        string='Lineas de costo de emision', comodel_name='account.share.cost.line')
    created_share_cost_line_id = fields.Many2one(
        string='Lineas de costo de emision creadas', comodel_name='account.share.cost.line')
