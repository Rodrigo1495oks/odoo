# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = ['res.config.settings']

    # IO fields
    lock_confirmed_io = fields.Boolean(
        "Lock Confirmed Orders", default=lambda self: self.env.company.io_lock == 'lock')
    io_double_validation = fields.Selection(
        related='company_id.io_double_validation', string="Levels of Approvals *", readonly=False)
    io_double_validation_amount = fields.Monetary(
        related='company_id.io_double_validation_amount', string="Minimum Amount", currency_field='company_currency_id', readonly=False)
    io_lock = fields.Selection(related='company_id.io_lock',
                               string="Purchase Order Modification *", readonly=False)
    io_order_approval = fields.Boolean(
        "Purchase Order Approval", default=lambda self: self.env.company.io_double_validation == 'two_step')

    po_lead = fields.Float(related='company_id.io_lead', readonly=False)
    use_po_lead = fields.Boolean(
        string="Security Lead Time for Purchase",
        config_parameter='higher_authority.use_io_lead',
        help="Margin of error for vendor lead times. When the system generates Purchase Orders for reordering products,they will be scheduled that many days earlier to cope with unexpected vendor delays.")

    @api.onchange('use_po_lead')
    def _onchange_use_po_lead(self):
        if not self.use_po_lead:
            self.po_lead = 0.0

    def set_values(self):
        super().set_values()
        io_lock = 'lock' if self.lock_confirmed_io else 'edit'
        io_double_validation = 'two_step' if self.io_order_approval else 'one_step'
        if self.io_lock != io_lock:
            self.io_lock = io_lock
        if self.io_double_validation != io_double_validation:
            self.io_double_validation = io_double_validation

    # VALIDATIONS
    # FOR INTEGRATION ORDERS
    # ACCOUNTS

    

    property_account_subscription_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Cuenta de Acciones",
                                                       domain="[('internal_type', '=', 'asset_receivable'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Esta cuenta será usada para registrar los saldos de subscripción del accionista, cuenta que puede ser modificada en el partner",related='company_id.property_account_subscription_id',
                                                       required=True, config_parameter='higher_authority.property_account_subscription_id')
    property_account_shareholding_id = fields.Many2one('account.account', company_dependent=True,related='company_id.property_account_shareholding_id',
                                                       string="Cuenta de Capital Suscripto",
                                                       domain="[('internal_type', '=', 'equity'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Esta cuenta será usada para las para registrar las acciones en una cuenta de capital, a pesar que sea establecida una cuenta por defecto diferente en el partner",
                                                       required=True, related='company_id.property_account_shareholding_id',
                                                       required=True, config_parameter='higher_authority.property_account_shareholding_id')
    property_account_integration_id = fields.Many2one('account.account', company_dependent=True,related='company_id.property_account_integration_id',
                                                      string="Cuenta de Capital Integrado",
                                                      domain="[('internal_type', '=', 'equity'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                      help="Esta cuenta será usada para las para registrar las acciones en una cuenta de capital, a pesar que sea establecida una cuenta por defecto diferente en el partner",
                                                      required=True, related='company_id.property_account_integration_id',config_parameter='higher_authority.property_account_integration_id')
    property_account_contribution_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Cuenta de Aportes",
                                                       domain="[('internal_type', '=', 'contribution'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",related='company_id.property_account_contribution_id',
                                                       help="Esta cuenta será usada para las para registrar los partes pendientes de aprobación, a pesar que sea establecida una cuenta por defecto diferente",
                                                       required=True, related='company_id.property_account_contribution_id',config_parameter='higher_authority.property_account_contribution_id')
    property_account_contribution_losses_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Cuenta de Aportes",
                                                       domain="[('internal_type', '=', 'contribution_losses'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Aportes para absorber pérdidas acumuladas",
                                                       required=True, related='company_id.property_account_contribution_losses_id',config_parameter='higher_authority.property_account_contribution_losses_id')
    property_account_issue_discount_id = fields.Many2one('account.account', company_dependent=True,
                                                         string="Descuentos de Capital",
                                                         domain="[('internal_type', '=', 'equity_issue_discount'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                         help="Esta cuenta será usada para las para registrar los Descuentos de Emisión",
                                                         required=True, related='company_id.property_account_issue_discount_id',config_parameter='higher_authority.property_account_issue_discount_id')
    property_account_issue_premium_id = fields.Many2one('account.account', company_dependent=True,
                                                        string="Primas de Emisión",
                                                        domain="[('internal_type', '=', 'equity_issue_premium'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                        help="Esta cuenta será usada para las para registrar las primas de emision de acciones, a pesar que sea establecida una cuenta por defecto diferente",
                                                        required=True, related='company_id.property_account_issue_premium_id',config_parameter='higher_authority.property_account_issue_premium_id')
    property_account_portfolio_shares = fields.Many2one('account.account', company_dependent=True,
                                                        string="Acciones en Cartera",
                                                        domain="[('internal_type', '=', 'equity_portfolio_shares'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                        help="Esta cuenta será usada para las para registrar el rescate de acciones en carteera",
                                                        required=True, related='company_id.property_account_portfolio_shares',config_parameter='higher_authority.property_account_portfolio_shares')
    account_capital_adjustment = fields.Many2one('account.account', company_dependent=True,
                                                 string="Ajuste al capital",
                                                 domain="[('internal_type', '=', 'equity_adjustment'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                 help="Esta cuenta será usada para las para registrar los ajustes de capital, a pesar que sea establecida una cuenta por defecto diferente",
                                                 required=True, related='company_id.account_capital_adjustment',config_parameter='higher_authority.account_capital_adjustment')

    account_shareholders_for_redemption_of_shares = fields.Many2one('account.account', company_dependent=True,
                                                                    string="Accionistas por rescates de acciones",
                                                                    domain="[('internal_type', '=', 'liability_payable_redemption_shares'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                                    help="Esta cuenta será usada para las para registrar las deuda con los accionistas, a quienes debe reintegrarseles el valor de mercado de las acciones vendidas (Deudas)",
                                                                    required=True,  related='company_id.account_shareholders_for_redemption_of_shares',config_parameter='higher_authority.account_shareholders_for_redemption_of_shares')
    account_share_redemption_discount = fields.Many2one('account.account', company_dependent=True,
                                                        string="Descuentos por rescates de acciones",
                                                        domain="[('internal_type', '=', 'contribution'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                        help="Esta cuenta será usada para las para registrar los Descuentos por rescates de acciones",
                                                        required=True, related='company_id.account_share_redemption_discount',config_parameter='higher_authority.account_share_redemption_discount')

    percentage_redemption = fields.Float(string='Porcentaje de rescate', help='Porcentaje fijado por la Gerencia para el pago en efectivo por cancelación de acciones',
                                         config_parameter='higher_authority.percentage_redemption', related='company_id.percentage_redemption',default=0.0, readonly=True)


    # """Campos usados para la emision y gestion de los bonos"""

    account_financial_expenses = fields.Many2one('account.account', company_dependent=True,
                                                 string="Otros Gastos Financieros",
                                                 domain="[('internal_type', '=', 'other_expenses'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                 help="Cuenta de gasto para registrar las erogacion por emision de obligaciones negociables",
                                                 required=True, related='company_id.account_financial_expenses',config_parameter='higher_authority.account_financial_expenses')

    account_cert_payable = fields.Many2one('account.account', company_dependent=True,
                                           string="Cuenta Bonos a pagar",
                                           domain="[('internal_type', '=', 'payable_negociable_obligations'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                           help="Cuenta de Pasivo para registrar las emisiones de obligaciones negociables",
                                           required=True, related='company_id.account_cert_payable',config_parameter='higher_authority.account_cert_payable')
    

    account_cert_interest = fields.Many2one('account.account', company_dependent=True,
                                           string="Intereses de obligaciones y bonos",
                                           domain="[('internal_type', '=', 'expenses_interest_and_implicit_financial_components'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                           help="Cuenta de Resultado para registrar el acaecimiento de los interes periodicos",
                                           required=True, related='company_id.account_cert_interest',related='company_id.account_cert_interest',config_parameter='higher_authority.account_cert_interest')
    
    account_receivable_cert=fields.Many2one('account.account', company_dependent=True,
                                           string="Intereses de obligaciones y bonos",
                                           domain="[('internal_type', '=', 'asset_receivable'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                           help="Cuenta para registrar el saldo pendiente que el tenedor de bonos debe abonar",
                                           required=True, related='company_id.account_receivable_cert',config_parameter='higher_authority.account_receivable_cert')
    
    account_cert_amortized=fields.Many2one('account.account', company_dependent=True,
                                           string="Obligaciones Amortizadas",
                                           domain="[('internal_type', '=', 'liability_payable_amortized'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                           help="Cuenta para registrar el saldo pendiente que amortizado que el tenedor de bonos debe abonar",
                                           required=True, related='company_id.account_cert_amortized',config_parameter='higher_authority.account_cert_amortized' )
    
    # Reservas
    account_legal_reserve=fields.Many2one('account.account', company_dependent=True,
                                           string="Reserva Legal",
                                           domain="[('internal_type', '=', 'legal_reserve'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                           help="Cuenta Única para registrar el saldo de la Reserva Legal",
                                           required=True,related='company_id.account_legal_reserve',config_parameter='higher_authority.account_legal_reserve' )