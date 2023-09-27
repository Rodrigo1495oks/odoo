# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from bisect import bisect_left
from collections import defaultdict
import re


class AccountFiscalYear(models.Model):
    _name = "account.fiscal.year"
    _inherit = ['account.fiscal.year']

    state = fields.Selection(string='Estado', selection=[('closed', 'Cerrado'), ('open', 'Abierto')],
                             help='Indique si el año fiscal esta abierto o cerrado, solo puede haber un año fiscal en curso')

    @api.constrains('state')
    def _check_state(self):
        for fy in self:
            # Busco todos los años fiscales registrados
            closed_year = self.search([('state', '=', 'open')], limit=1)
            if closed_year:
                raise ValidationError(
                    _(
                        "Ya existe otro período fiscal en curso. \n"
                        "Antes de crear otro debe cerrar el anterior.\n"
                        "'{closed_year}'"
                    ).format(
                        closed_year=closed_year.display_name
                    ))