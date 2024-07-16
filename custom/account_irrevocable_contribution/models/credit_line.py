# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from functools import lru_cache
from pytz import timezone, UTC
from markupsafe import Markup
from odoo.exceptions import UserError
from datetime import datetime, timedelta, timezone, time
from odoo.tools.float_utils import float_is_zero, float_compare, float_round
from odoo import models, fields, api, tools, _
from odoo.osv.expression import get_unaccent_wrapper
from odoo.exceptions import ValidationError
from odoo.addons.base.models.res_partner import _tz_get
from odoo.tools.misc import get_lang
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, relativedelta, format_amount, format_date, formatLang, get_lang, \
    groupby
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError

class SoCreditLine(models.Model):
    _inherit = 'account.suscription.credit.line'

    contribution_id=fields.Many2one(string='Contribution Order', comodel_name='account.irrevocable.contribution', readonly=True)

    contribution_line_ids = fields.One2many(comodel_name='account.move.line', inverse_name='contribution_credit_line_id',
                                           string="Contribution Lines",
                                           readonly=True, copy=False,
                                           domain=[('move_id.move_type', '=', 'contribution')])