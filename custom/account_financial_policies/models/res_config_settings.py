# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = ['res.config.settings']
    company_id = fields.Many2one(string='Compañía', comodel_name='res.company', default=lambda self: self.env.company)
    # IO fields
    company_currency_id = fields.Many2one(
        'res.currency', 'Valuation Currency', related='company_id.currency_id',
        help="Technical field to correctly show the currently selected company's currency that corresponds "
             "to the totaled value of the product's valuation layers")
    lock_confirmed_io = fields.Boolean(
        "Lock Confirmed Orders", default=lambda self: self.env.company.io_lock == 'lock')
    io_double_validation = fields.Selection(
        related='company_id.io_double_validation', string="Levels of Approvals *", readonly=False)
    io_double_validation_amount = fields.Monetary(
        related='company_id.io_double_validation_amount', string="Minimum Amount", currency_field='company_currency_id',
        readonly=False)
    io_lock = fields.Selection(related='company_id.io_lock',
                               string="Purchase Order Modification *", readonly=False)
    io_order_approval = fields.Boolean(
        "Purchase Order Approval", default=lambda self: self.env.company.io_double_validation == 'two_step')

    po_lead = fields.Float(related='company_id.io_lead', readonly=False)
    use_po_lead = fields.Boolean(
        string="Security Lead Time for Purchase",
        config_parameter='account_financial_policies.use_io_lead',
        help="Margin of error for vendor lead times. When the system generates Purchase Orders for reordering products,they will be scheduled that many days earlier to cope with unexpected vendor delays.")

    # JOURNALS

    subscription_journal_id = fields.Many2one('account.journal', company_dependent=True, readonly=False,
                                              string="Subscription Journal",
                                              domain="[('type', '=', 'suscription'),('company_id', '=', current_company_id)]",
                                              help="Diario para registrar suscripciones e integraciones",
                                              related='company_id.subscription_journal_id',
                                              config_parameter='account_financial_policies.subscription_journal_id'
                                              )

    property_account_shareholding_id = fields.Many2one('account.account', company_dependent=True, readonly=False,
                                                       string="Cuenta de Capital Suscripto",
                                                       domain="[('account_type', '=', 'equity'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                                       help="Esta cuenta será usada para las para registrar las acciones en una cuenta de capital, a pesar que sea establecida una cuenta por defecto diferente en el partner",
                                                       related='company_id.property_account_shareholding_id',
                                                       config_parameter='account_financial_policies.property_account_shareholding_id')

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

    forecast_integration_account=fields.Many2one(string='Forecast Integration Account',
                                                 comodel_name='account.account',
                                                 help='Cuenta de Previsión para ingresos de materiales pendientes de Integración',
                                                 domain="[('account_type','=','liability_payable_forecast'), ('deprecated', '=', False), ('company_id', '=', company_id)]",
                                                 related='company_id.forecast_integration_account',
                                                 config_parameter='account_financial_policies.forecast_integration_account',
                                                 )

    # ACCOUNTS
    share_price = fields.Float(string='Precio de las Acciones', help='Valor Nominal para emitir acciones',
                               readonly=False,
                               company_dependent=True, related='company_id.share_price',
                               config_parameter='account_financial_policies.share_price')
    property_account_subscription_id = fields.Many2one('account.account', company_dependent=True, readonly=False,
                                                       string="Cuenta de Acciones",
                                                       domain="[('account_type', '=', 'asset_receivable_others'), ('deprecated', '=', False), ('company_id', '=', company_id)]",
                                                       help="Esta cuenta será usada para registrar los saldos de subscripción del accionista, cuenta que puede ser modificada en el partner",
                                                       related='company_id.property_account_subscription_id',
                                                       config_parameter='account_financial_policies.property_account_subscription_id', )
    property_account_shareholding_id = fields.Many2one('account.account', company_dependent=True, readonly=False,
                                                       string="Cuenta de Capital Suscripto",
                                                       domain="[('account_type', '=', 'equity'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                                       help="Esta cuenta será usada para las para registrar las acciones en una cuenta de capital, a pesar que sea establecida una cuenta por defecto diferente en el partner",
                                                       related='company_id.property_account_shareholding_id',
                                                       config_parameter='account_financial_policies.property_account_shareholding_id')
    property_account_integration_id = fields.Many2one('account.account', company_dependent=True, readonly=False,
                                                      string="Cuenta de Capital Integrado",
                                                      domain="[('account_type', '=', 'equity'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                                      help="Esta cuenta será usada para las para registrar las acciones en una cuenta de capital, a pesar que sea establecida una cuenta por defecto diferente en el partner",
                                                      related='company_id.property_account_integration_id',
                                                      config_parameter='account_financial_policies.property_account_integration_id')
    property_account_contribution_id = fields.Many2one('account.account', company_dependent=True, readonly=False,
                                                       string="Cuenta de Aportes",
                                                       domain="[('account_type', '=', 'contribution'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                                       related='company_id.property_account_contribution_id',
                                                       help="Esta cuenta será usada para las para registrar los partes pendientes de aprobación, a pesar que sea establecida una cuenta por defecto diferente",
                                                       config_parameter='account_financial_policies.property_account_contribution_id')
    property_account_contribution_losses_id = fields.Many2one('account.account', company_dependent=True, readonly=False,
                                                              string="Cuenta de Aportes",
                                                              domain="[('account_type', '=', 'contribution_losses'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                                              help="Aportes para absorber pérdidas acumuladas",
                                                              related='company_id.property_account_contribution_losses_id',
                                                              config_parameter='account_financial_policies.property_account_contribution_losses_id')
    property_account_issue_discount_id = fields.Many2one('account.account', company_dependent=True, readonly=False,
                                                         string="Descuentos de Capital",
                                                         domain="[('account_type', '=', 'equity_issue_discount'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                                         help="Esta cuenta será usada para las para registrar los Descuentos de Emisión",
                                                         related='company_id.property_account_issue_discount_id',
                                                         config_parameter='account_financial_policies.property_account_issue_discount_id')
    property_account_issue_premium_id = fields.Many2one('account.account', company_dependent=True, readonly=False,
                                                        string="Primas de Emisión",
                                                        domain="[('account_type', '=', 'equity_issue_premium'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                                        help="Esta cuenta será usada para las para registrar las primas de emision de acciones, a pesar que sea establecida una cuenta por defecto diferente",
                                                        related='company_id.property_account_issue_premium_id',
                                                        config_parameter='account_financial_policies.property_account_issue_premium_id')
    property_account_portfolio_shares = fields.Many2one('account.account', company_dependent=True, readonly=False,
                                                        string="Acciones en Cartera",
                                                        domain="[('account_type', '=', 'equity_portfolio_shares'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                                        help="Esta cuenta será usada para las para registrar el rescate de acciones en carteera",
                                                        related='company_id.property_account_portfolio_shares',
                                                        config_parameter='account_financial_policies.property_account_portfolio_shares')
    account_capital_adjustment = fields.Many2one('account.account', company_dependent=True, readonly=False,
                                                 string="Ajuste al capital",
                                                 domain="[('account_type', '=', 'equity_adjustment'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                                 help="Esta cuenta será usada para las para registrar los ajustes de capital, a pesar que sea establecida una cuenta por defecto diferente",
                                                 related='company_id.account_capital_adjustment',
                                                 config_parameter='account_financial_policies.account_capital_adjustment')

    account_shareholders_for_redemption_of_shares = fields.Many2one('account.account', company_dependent=True,
                                                                    readonly=False,
                                                                    string="Accionistas por rescates de acciones",
                                                                    domain="[('account_type', '=', 'liability_payable_dividends_redemption_shares'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                                                    help="Esta cuenta será usada para las para registrar las deuda con los accionistas, a quienes debe reintegrarseles el valor de mercado de las acciones vendidas (Deudas)",
                                                                    related='company_id.account_shareholders_for_redemption_of_shares',
                                                                    config_parameter='account_financial_policies.account_shareholders_for_redemption_of_shares')
    account_share_redemption_discount = fields.Many2one('account.account', company_dependent=True, readonly=False,
                                                        string="Descuentos por rescates de acciones",
                                                        domain="[('account_type', '=', 'contribution'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                                        help="Esta cuenta será usada para las para registrar los Descuentos por rescates de acciones",
                                                        related='company_id.account_share_redemption_discount',
                                                        config_parameter='account_financial_policies.account_share_redemption_discount')

    percentage_redemption = fields.Float(string='Porcentaje de rescate',
                                         help='Porcentaje fijado por la Gerencia para el pago en efectivo por cancelación de acciones',
                                         config_parameter='account_financial_policies.percentage_redemption',
                                         related='company_id.percentage_redemption', default=0.0, readonly=False, )

    # """Campos usados para la emision y gestion de los bonos"""

    account_financial_expenses = fields.Many2one('account.account', company_dependent=True,
                                                 string="Otros Gastos Financieros", readonly=False,
                                                 domain="[('account_type', '=', 'expense_financial'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                                 help="Cuenta de gasto para registrar las erogacion por emision de obligaciones negociables",
                                                 related='company_id.account_financial_expenses',
                                                 config_parameter='account_financial_policies.account_financial_expenses')

    account_cert_payable = fields.Many2one('account.account', company_dependent=True,
                                           string="Cuenta Bonos a pagar", readonly=False,
                                           domain="[('account_type', '=', 'liability_payable_financial'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                           help="Cuenta de Pasivo para registrar las emisiones de obligaciones negociables",
                                           related='company_id.account_cert_payable',
                                           config_parameter='account_financial_policies.account_cert_payable')

    account_cert_interest = fields.Many2one('account.account', company_dependent=True, readonly=False,
                                            string="Intereses de obligaciones y bonos",
                                            domain="[('account_type', '=', 'expense_financial'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                            help="Cuenta de Resultado para registrar el acaecimiento de los interes periodicos",
                                            related='company_id.account_cert_interest',
                                            config_parameter='account_financial_policies.account_cert_interest')

    account_receivable_cert = fields.Many2one('account.account', company_dependent=True, readonly=False,
                                              string="Intereses de obligaciones y bonos",
                                              domain="[('account_type', '=', 'asset_receivable_others'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                              help="Cuenta para registrar el saldo pendiente que el tenedor de bonos debe abonar",
                                              related='company_id.account_receivable_cert',
                                              config_parameter='account_financial_policies.account_receivable_cert')

    account_cert_amortized = fields.Many2one('account.account', company_dependent=True, readonly=False,
                                             string="Obligaciones Amortizadas",
                                             domain="[('account_type', '=', 'liability_payable_financial_amortized'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                             help="Cuenta para registrar el saldo pendiente que amortizado que el tenedor de bonos debe abonar",
                                             related='company_id.account_cert_amortized',
                                             config_parameter='account_financial_policies.account_cert_amortized')

    # Reservas
    account_legal_reserve = fields.Many2one('account.account', company_dependent=True, readonly=False,
                                            string="Reserva Legal",
                                            domain="[('account_type', '=', 'legal_reserve'),('deprecated', '=', False), ('company_id', '=', company_id)]",
                                            help="Cuenta Única para registrar el saldo de la Reserva Legal",
                                            related='company_id.account_legal_reserve',
                                            config_parameter='account_financial_policies.account_legal_reserve')
