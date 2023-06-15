# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import collections
from functools import lru_cache
import hashlib
from itertools import groupby
import re
import pytz
import requests
import math
import babel.dates
import logging

from odoo.exceptions import UserError
from werkzeug import urls

from datetime import datetime, timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api, tools, _

from odoo.osv.expression import get_unaccent_wrapper

from odoo.exceptions import ValidationError

from odoo.addons.base.models.res_partner import _tz_get
from odoo.addons.calendar.models.calendar_attendee import Attendee
from odoo.addons.calendar.models.calendar_recurrence import weekday_to_field, RRULE_TYPE_SELECTION, END_TYPE_SELECTION, MONTH_BY_SELECTION, WEEKDAY_SELECTION, BYDAY_SELECTION
from odoo.tools.translate import _
from odoo.tools.misc import get_lang
from odoo.tools import pycompat
from odoo.exceptions import UserError, AccessError


class CapitalReductionType(models.Model):
    _name = 'capital.reduction.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Objeto Typo Reducción de Acciones'
    # _order = 'short_name desc, name desc'
    # _rec_name = 'short_name'

    # metodos computados

    name = fields.Char(string='Nombre', required=True)

    profit_lost_account = fields.Many2one(
        string='Cuenta de resultados no Asignados', comodel_name='account.account')

    counterpart_account = fields.Many2one(
        string='Contrapartida', comodel_name='account.account')
