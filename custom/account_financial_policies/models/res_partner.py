# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError

from odoo.tools.translate import _

from datetime import timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api

from odoo.exceptions import ValidationError


class Partner(models.Model):
    _inherit = 'res.partner'
    _name = 'res.partner'
    # specie_id = fields.Many2one(string='Especie', comodel_name='species')



    shareholder_rank = fields.Integer(default=0, copy=False)
    # priority = fields.Selection(
    #     [('0', 'Normal'), ('1', 'Urgent')], 'Priority', default='0', index=True)

    
        # ACCOUNTS

    property_account_subscription_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Cuenta de Acciones",
                                                       domain="[('account_type', '=', 'asset_receivable_others'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Esta cuenta será usada para registrar los saldos de subscripción del accionista, cuenta que puede ser modificada en el partner",
                                                       required=False)
    property_account_shareholding_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Cuenta de Capital Suscripto",
                                                       domain="[('account_type', '=', 'equity'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Esta cuenta será usada para las para registrar las acciones en una cuenta de capital, a pesar que sea establecida una cuenta por defecto diferente en el partner",
                                                       required=False)
    property_account_integration_id = fields.Many2one('account.account', company_dependent=True,
                                                      string="Cuenta de Capital Integrado",
                                                      domain="[('account_type', '=', 'equity'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                      help="Esta cuenta será usada para las para registrar las acciones en una cuenta de capital, a pesar que sea establecida una cuenta por defecto diferente en el partner",
                                                      required=False)
    property_account_contribution_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Cuenta de Aportes",
                                                       domain="[('account_type', '=', 'contribution'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Esta cuenta será usada para las para registrar los partes pendientes de aprobación, a pesar que sea establecida una cuenta por defecto diferente",
                                                       required=False)
    property_account_contribution_losses_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Cuenta de Aportes",
                                                       domain="[('account_type', '=', 'contribution_losses'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Aportes para absorber pérdidas acumuladas",
                                                       required=False)
    property_account_contribution_credits_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Saldo de aportes no integrados",
                                                       domain="[('account_type', '=', 'asset_receivable_others'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Esta cuenta será usada para las para registrar los partes pendientes de pago, a pesar que sea establecida una cuenta por defecto diferente",
                                                       required=False, )
    property_account_issue_discount_id = fields.Many2one('account.account', company_dependent=True,
                                                         string="Descuentos de Emisión",
                                                         domain="[('account_type', '=', 'equity_issue_discount'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                         help="Esta cuenta será usada para las para registrar los pagos de aportes, a pesar que sea establecida una cuenta por defecto diferente",
                                                         required=False)
    property_account_issue_premium_id = fields.Many2one('account.account', company_dependent=True,
                                                        string="Primas de Emisión",
                                                        domain="[('account_type', '=', 'equity_issue_premium'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                        help="Esta cuenta será usada para las para registrar las primas de emision de acciones, a pesar que sea establecida una cuenta por defecto diferente",
                                                        required=False)
    
    account_capital_adjustment = fields.Many2one('account.account', company_dependent=True,
                                                 string="Ajuste al capital",
                                                 domain="[('account_type', '=', 'equity_adjustment'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                 help="Esta cuenta será usada para las para registrar los ajustes de capital, a pesar que sea establecida una cuenta por defecto diferente",
                                                 required=False)

    account_shareholders_for_redemption_of_shares = fields.Many2one('account.account', company_dependent=True,
                                                                    string="Accionistas por rescates de acciones",
                                                                    domain="[('account_type', '=', 'liability_payable_dividends_redemption_shares'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                                    help="Esta cuenta será usada para las para registrar los pagos de aportes, a pesar que sea establecida una cuenta por defecto diferente",
                                                                    required=False, )

    # """Campos usados para la emision y gestion de los bonos"""

    account_cert_payable = fields.Many2one('account.account', company_dependent=True,
                                           string="Cuenta Bonos a pagar",
                                           domain="[('account_type', '=', 'liability_payable_financial'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                           help="Cuenta de Pasivo para registrar las emisiones de obligaciones negociables",
                                           required=False, config_parameter='higher_authority.account_cert_payable')
    account_receivable_cert=fields.Many2one('account.account', company_dependent=True,
                                           string="Créditos por bonos",
                                           domain="[('account_type', '=', 'asset_receivable_others'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                           help="Cuenta para registrar el saldo pendiente que eel tenedor de bonos debe abonar",
                                           required=False )
    # LOW LEVEL METHODS
    @api.model_create_multi
    def create(self, vals_list):
        search_partner_mode = self.env.context.get('res_partner_search_mode')
        is_shareholder = search_partner_mode == 'shareholder'
        if search_partner_mode:
            for vals in vals_list:
                if is_shareholder and 'shareholder_rank' not in vals:
                    vals['shareholder_rank'] = 1
        return super().create(vals_list)