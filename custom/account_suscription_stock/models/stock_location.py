# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockLocation(models.Model):
    _inherit = "stock.location"

    forecast_integration_account = fields.Many2one(string='Forecast Integration Account',
                                                   comodel_name='account.account',
                                                   help='Cuenta de Previsión para ingresos de materiales pendientes de Integración',
                                                   domain="[('account_type','=','liability_payable_forecast'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                   )