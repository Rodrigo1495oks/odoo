# -*- coding: utf-8 -*-

from odoo import api, fields, models, _, tools
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime, timedelta, date
import re


class AccountFiscalPeriod(models.Model):
    _name = "account.fiscal.period"
    _description = 'Objeto Subscripción de Acciones'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'

    def _get_valid_years(self):
        lst = []
        for year in range(1900, 2030):
            lst.append(f'{year}', year)
        return lst

    name = fields.Char(string='Período Fiscal')

    state = fields.Selection(string='Estado', selection=[('closed', 'Cerrado'), ('open', 'Abierto')],
                             help='Indique si el periodo fiscal esta abierto o cerrado', readonly=True)
    year = fields.Selection(string='Año', default='2020',
                            selection=_get_valid_years)
    short_name = fields.Char(string='Referencia', default='New',
                             required=True, copy=False, readonly=True)
    start_date = fields.Date(string='Inicio')
    end_date = fields.Date(string='Final')

    op_cl = fields.Boolean(string='Per. de Cierre/Apertura',
                           help='Indique si es el útlimo o primer periodo', readonly=True)

    fiscal_year = fields.Many2one(
        string='Año Fiscal', comodel_name='account.fiscal.year', help='Año Fiscal Asociado', readonly=True)

    # Actions
    def action_open_period(self):
        if self.state == 'closed' and self.fiscal_year.state == 'open':
            self.state = 'open'
        else:
            raise UserError('Error: No puede abrir el periodo')

    def action_close_period(self):
        if self.state == 'open' and self.fiscal_year.state == 'open':
            self.state = 'closed'
        else:
            raise UserError('Error: No puede cerrar el periodo')
        
    # LOW LEVELS METHODS

    @api.model
    def create(self, vals):
        if vals.get('short_name', _('New')) == _('New'):
            vals['short_name'] = (self.env['ir.sequence'].next_by_code(
                'account.fiscal.period')) or _('New')
        res = super(AccountFiscalPeriod, self.create(vals))
        return res
