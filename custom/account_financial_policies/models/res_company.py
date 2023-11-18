# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _name = "res.company"
    _inherit = 'res.company'

    # VALIDATIONS
    # FOR INTEGRATION ORDERS
    io_lead = fields.Float(string='Integration Order Lead Time', required=True,
        help="Margin of error for vendor lead times. When the system "
             "generates Integration Orders for procuring products, "
             "they will be scheduled that many days earlier "
             "to cope with unexpected vendor delays.", default=0.0)

    io_lock = fields.Selection([
        ('edit', 'Allow to edit Integration orders'),
        ('lock', 'Confirmed integration orders are not editable')
        ], string="Integration Order Modification", default="edit",
        help='Integration Order Modification used when you want to Integration order editable after confirm')
    io_double_validation = fields.Selection([
        ('one_step', 'Confirm Integration Orders in one step'),
        ('two_step', 'Get 2 levels of approvals to confirm a Integration Order')
    ], string="Levels of Approvals", default='one_step',
        help="Provide a double validation mechanism for Integration")
    
    io_double_validation_amount = fields.Monetary(string='Double validation amount', default=50000000,
        help="Minimum amount for which a double validation is required")
    
    # ACCOUNTS

    
    property_account_subscription_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Cuenta de Acciones",
                                                       domain="[('internal_type', '=', 'receivable'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Esta cuenta será usada para registrar los saldos de subscripción del accionista, cuenta que puede ser modificada en el partner",
                                                       required=True, )
    property_account_shareholding_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Cuenta de Capital Suscripto",
                                                       domain="[('internal_type', '=', 'equity'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Esta cuenta será usada para las para registrar las acciones en una cuenta de capital, a pesar que sea establecida una cuenta por defecto diferente en el partner",
                                                       required=True, )
    property_account_integration_id = fields.Many2one('account.account', company_dependent=True,
                                                      string="Cuenta de Capital Integrado",
                                                      domain="[('internal_type', '=', 'equity'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                      help="Esta cuenta será usada para las para registrar las acciones en una cuenta de capital, a pesar que sea establecida una cuenta por defecto diferente en el partner",
                                                      required=True, )
    property_account_contribution_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Cuenta de Aportes",
                                                       domain="[('internal_type', '=', 'contribution'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Esta cuenta será usada para las para registrar los partes pendientes de aprobación, a pesar que sea establecida una cuenta por defecto diferente",
                                                       required=True, )
    property_account_contribution_losses_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Cuenta de Aportes",
                                                       domain="[('internal_type', '=', 'contribution_losses'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Aportes para absorber pérdidas acumuladas",
                                                       required=True)
    property_account_contribution_credits_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Saldo de aportes no integrados",
                                                       domain="[('internal_type', '=', 'contribution_credits'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Esta cuenta será usada para las para registrar los partes pendientes de pago, a pesar que sea establecida una cuenta por defecto diferente",
                                                       required=True, )
    

    property_account_issue_discount_id = fields.Many2one('account.account', company_dependent=True,
                                                         string="Descuentos de Capital",
                                                         domain="[('internal_type', '=', 'equity_issue_discount'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                         help="Esta cuenta será usada para las para registrar los pagos de aportes, a pesar que sea establecida una cuenta por defecto diferente",
                                                         required=True, )
    property_account_issue_premium_id = fields.Many2one('account.account', company_dependent=True,
                                                        string="Primas de Emisión",
                                                        domain="[('internal_type', '=', 'equity_issue_premium'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                        help="Esta cuenta será usada para las para registrar las primas de emision de acciones, a pesar que sea establecida una cuenta por defecto diferente",
                                                        required=True, )
    property_account_portfolio_shares = fields.Many2one('account.account', company_dependent=True,
                                                        string="Acciones en Cartera",
                                                        domain="[('internal_type', '=', 'equity_portfolio_shares'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                        help="Esta cuenta será usada para las para registrar el rescate de acciones en carteera",
                                                        required=True, )
    account_capital_adjustment = fields.Many2one('account.account', company_dependent=True,
                                                 string="Ajuste al capital",
                                                 domain="[('internal_type', '=', 'equity_adjustment'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                 help="Esta cuenta será usada para las para registrar los ajustes de capital, a pesar que sea establecida una cuenta por defecto diferente",
                                                 required=True, )

    account_shareholders_for_redemption_of_shares = fields.Many2one('account.account', company_dependent=True,
                                                                    string="Accionistas por rescates de acciones",
                                                                    domain="[('internal_type', '=', 'liability_payable_redemption_shares'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                                    help="Esta cuenta será usada para las para registrar los pagos de aportes, a pesar que sea establecida una cuenta por defecto diferente",
                                                                    required=True)
    account_share_redemption_discount = fields.Many2one('account.account', company_dependent=True,
                                                        string="Descuentos por rescates de acciones",
                                                        domain="[('internal_type', '=', 'contribution'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                        help="Esta cuenta será usada para las para registrar los pagos de aportes, a pesar que sea establecida una cuenta por defecto diferente",
                                                        required=True, )

    percentage_redemption = fields.Float(string='Porcentaje de rescate', help='Porcentaje fijado por la Gerencia para el pago en efectivo por cancelación de acciones', default=0.0)


    # """Campos usados para la emision y gestion de los bonos"""

    account_financial_expenses = fields.Many2one('account.account', company_dependent=True,
                                                 string="Otros Gastos Financieros",
                                                 domain="[('internal_type', '=', 'expense_financial'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                 help="Cuenta de gasto para registrar las erogacion por emision de obligaciones negociables",
                                                 required=True)

    account_cert_payable = fields.Many2one('account.account', company_dependent=True,
                                           string="Cuenta Bonos a pagar",
                                           domain="[('internal_type', '=', 'payable_negociable_obligations'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                           help="Cuenta de Pasivo para registrar las emisiones de obligaciones negociables",
                                           required=True)
    

    account_cert_interest = fields.Many2one('account.account', company_dependent=True,
                                           string="Intereses de obligaciones y bonos",
                                           domain="[('internal_type', '=', 'expenses_interest_and_implicit_financial_components'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                           help="Cuenta de Resultado para registrar el acaecimiento de los interes periodicos",
                                           required=True)
    
    account_receivable_cert=fields.Many2one('account.account', company_dependent=True,
                                           string="Intereses de obligaciones y bonos",
                                           domain="[('internal_type', '=', 'asset_receivable'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                           help="Cuenta para registrar el saldo pendiente que eel tenedor de bonos debe abonar",
                                           required=True )
    account_cert_amortized=fields.Many2one('account.account', company_dependent=True,
                                           string="Obligaciones Amortizadas",
                                           domain="[('internal_type', '=', 'liability_payable_amortized'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                           help="Cuenta para registrar el saldo pendiente que amortizado que el tenedor de bonos debe abonar",
                                           required=True)
    # Reservas

    account_legal_reserve=fields.Many2one('account.account', company_dependent=True,
                                           string="Reserva Legal",
                                           domain="[('internal_type', '=', 'legal_reserve'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                           help="Cuenta Única para registrar el saldo de la Reserva Legal",
                                           required=True)