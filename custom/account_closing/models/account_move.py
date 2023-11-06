import ast
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta
from functools import lru_cache

from odoo import api, fields, models, Command, _
from odoo.tools import frozendict, formatLang, format_date, float_compare, Query
from odoo.tools.sql import create_index

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
# from odoo.addons.account.tools import format_rf_reference
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



class AccountMove(models.Model):
    # _name = "account.move"
    _inherit = "account.move"

    @api.depends('move_type')
    def _compute_available_fy(self):
        available_fy = self.env['account.fiscal.year'].search(
            [('state', '=', 'open')])
        for am in self:
            for fy in available_fy:
                # Verificar esto
                am.fiscal_year = (fy.date_from <= am.date <=
                                  fy.date_to for fy in available_fy)

    # defaults

    move_type = fields.Selection(
        selection_add=[
            ('year_closing_entry', 'Asiento de Cierre'),
        ]
    )

    fiscal_year = fields.Many2one(string='Año Fiscal', comodel_name='account.fiscal.year', help='Año Fiscal Relacionado',
                                  readonly=False, compute='_compute_available_fy', domain=[('state', '=', 'open')])
    fiscal_period = fields.Many2one(
        string='Período Fiscal', comodel_name='account.fiscal.period', help='Periodo Fiscal Relacionado', readonly=False, domain=[('fiscal_year', '=', 'fiscal_year')])

    # Constraints
    @api.constrains('fiscal_period', 'fiscal_year')
    def _validate_fiscal_period(self):
        company = self.env['res.company'].browse(am.company_id)
        for am in self:
            if company.restrict_fy and (am.fiscal_year.state == 'closed' or am.fiscal_period.state == 'closed'):
                raise ValidationError(
                    'No se puede crear asiento contables en periodos bloqueados! Consulte con el jefe del area de Contabilidad')
