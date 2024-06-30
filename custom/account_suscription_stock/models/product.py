# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import operator as py_operator
from ast import literal_eval
from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools import float_is_zero, check_barcode_encoding
from odoo.tools.float_utils import float_round
from odoo.tools.mail import html2plaintext, is_html_empty

OPERATORS = {
    '<': py_operator.lt,
    '>': py_operator.gt,
    '<=': py_operator.le,
    '>=': py_operator.ge,
    '=': py_operator.eq,
    '!=': py_operator.ne
}


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = 'product.template'

    forecast_integration_account = fields.Many2one(string='Forecast Integration Account',
                                                   comodel_name='account.account',
                                                   help='Cuenta de Previsión para ingresos de materiales pendientes de Integración',
                                                   domain="[('account_type','=','liability_payable_forecast'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                   )
    # -------------------------------------------------------------------------
    # Misc.
    # -------------------------------------------------------------------------
    def _get_product_accounts(self):
        """ Add the stock accounts related to product to the result of super()
        @return: dictionary which contains information regarding stock accounts and super (income+expense accounts)
        """
        accounts = super(ProductTemplate, self)._get_product_accounts()
        res = self._get_asset_accounts()
        accounts.update({
            'stock_integration_forecast': self.categ_id.property_stock_account_integration_categ_id
        })
        return accounts

class ProductCategory(models.Model):
    _inherit = "product.category"

    forecast_integration_account = fields.Many2one(string='Forecast Integration Account',
                                                   comodel_name='account.account',
                                                   help='Cuenta de Previsión para ingresos de materiales pendientes de Integración',
                                                   domain="[('account_type','=','liability_payable_forecast'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                   )