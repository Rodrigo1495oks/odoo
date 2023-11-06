# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _name = "res.company"
    _inherit = 'res.company'

    financial_year_result_account = fields.Many2one(
        string='Cuenta de Resultados del ejercicio', comodel_name='account.account', domain="[('internal_type', '=', 'equity_unaffected'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]",required=True,
                                                       help="Esta cuenta será usada para registrar los saldos de resultados del ejercicio, al saldar las cuentas de resultado",)
    restrict_fy = fields.Boolean(string='Restringir la creación de Asientos para Periodos/Años Cerrados', default=False,
                                 help='Indique si desea restringir la creacion de asientos contables para periodos o años fiscales cerrados')
