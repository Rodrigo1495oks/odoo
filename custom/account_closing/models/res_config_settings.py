# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _name = 'res.config.settings'
    _inherit = ['res.config.settings']

    financial_year_result_account = fields.Many2one(
        string='Cuenta de Resultados del ejercicio', comodel_name='account.account', config_parameter='higher_authority.financial_year_result_account', domain="[('internal_type', '=', 'equity_unaffected'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]", related='company_id.financial_year_result_account',
        help="Esta cuenta será usada para registrar los saldos de subscripción del accionista, a pesar que sea establecida una cuenta por defecto diferente",)

    restrict_fy = fields.Boolean(string='Restringir la creación de Asientos para Periodos/Años Cerrados', default=False,
                                 help='Indique si desea restringir la creacion de asientos contables para periodos o años fiscales cerrados', related='company_id.restrict_fy',config_parameter='account_closing.restrict_fy')
