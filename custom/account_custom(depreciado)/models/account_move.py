import ast
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta
from functools import lru_cache

from odoo import api, fields, models, Command, _
from odoo.tools import frozendict, formatLang, format_date, float_compare, Query
from odoo.tools.sql import create_index
from odoo.addons.web.controllers.utils import clean_action

from odoo.addons.account.models.account_move import MAX_HASH_VERSION

# -*- coding: utf-8 -*-

from collections import defaultdict
from contextlib import ExitStack, contextmanager
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from hashlib import sha256
from json import dumps
import re
from textwrap import shorten
from unittest.mock import patch


from odoo.addons.base.models.decimal_precision import DecimalPrecision
from odoo.addons.account.tools import format_rf_reference
from odoo.exceptions import UserError, ValidationError, AccessError, RedirectWarning
from odoo.tools import (
    date_utils,
    email_re,
    email_split,
    float_compare,
    float_is_zero,
    float_repr,
    format_amount,
    format_date,
    formatLang,
    frozendict,
    get_lang,
    is_html_empty,
    sql
)


MAX_HASH_VERSION = 3

TYPE_REVERSE_MAP = {
    'entry': 'entry',
    'out_invoice': 'out_refund',
    'out_refund': 'entry',
    'in_invoice': 'in_refund',
    'in_refund': 'entry',
    'out_receipt': 'entry',
    'in_receipt': 'entry',
}

EMPTY = object()


class AccountMove(models.Model):
    # _name = "account.move"
    _inherit = "account.move"

    move_type = fields.Selection(
        selection_add=[
            ('suscription', 'Suscription'),
            ('integration', 'Integration'),
            ('contribution', 'Aporte Irrevocable'),
            ('redemption', 'Rescate de Acciones'),
            ('share_sale', 'Venta de Acciones'),
            ('reduction', 'Reducción de Capital'),
            ('certificate', 'Emision de Bonos'),
        ]
    )

    integration_orders = fields.One2many(string='Orden de Integración', comodel_name='integration.order', inverse_name='suscription_order',
                                         help='Campo técnico usado para relacionar la orden de suscripcion ocn la de integracion respectiva')

    irrevocable_contribution = fields.One2many(
        string='Aporte Irrevocable', comodel_name='irrevocable.contribution')
    capital_reduction = fields.One2many(
        string='Reducción de Capital', comodel_name='capital.reduction')
