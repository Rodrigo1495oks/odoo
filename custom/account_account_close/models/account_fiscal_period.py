# -*- coding: utf-8 -*-

from odoo import api, fields, models, _, tools
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime, timedelta, date
import re

class AccountFiscalYear(models.Model):
    _name = "account.fiscal.year"
    _inherit = ['account.fiscal.year']

    name=fields.Char(string='Año Fiscal')
    
    state = fields.Selection(string='Estado', selection=[('closed', 'Cerrado'), ('open', 'Abierto')],
                             help='Indique si el periodo fiscal esta abierto o cerrado')
    year = fields.Selection(string='Año', default='2020',
                            compute='_compute_valid_years')
    short_name = fields.Char(string='Referencia', default='New',
                             required=True, copy=False, readonly=True)
    start_date=fields.Date(string='Inicio')
    end_date=fields.Date(string='Final')

    op_cl=fields.Boolean(string='Per. de Cierre/Apertura', help='Indique si es el útlimo o primer periodo', readonly=True)

    fiscal_year=fields.Many2one(string='Año Fiscal', comodel_name='account.fiscal.year', help='Año Fiscal Asociado')