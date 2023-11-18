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

    # specie_id = fields.Many2one(string='Especie', comodel_name='species')

    start_date = fields.Datetime(
        string='Fecha Inicio del cargo', readonly=True)
    end_date = fields.Datetime(string='Fecha de Finalización', readonly=True)
    date_of_birth = fields.Date(string='Fecha de Nacimiento', readonly=True)
    post_code = fields.Integer(string='Código Postal')
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Urgent')], 'Priority', default='0', index=True)

    # campos relacionales
    position = fields.Many2one(
        string='Cargo', help='Cargo del accionista dentro de la asamblea', comodel_name='account.shareholder.position')
    shares = fields.One2many(string='Acciones', comodel_name='account.share',
                             inverse_name='shareholder', store=True, help='Acciones que le pertenecen a este acconista')
    integration_orders = fields.One2many(
        string='Integraciones', comodel_name='integration.order', inverse_name='partner_id')
    subscription_orders = fields.One2many(
        string='Subscripciones', comodel_name='subscription.order', inverse_name='partner_id')
    # contabilidad
    # bank_account_id = fields.Many2one('res.partner.bank',
    #                                   string="Bank Account",
    #                                   ondelete='restrict', copy=False,
    #                                   check_company=True,
    #                                   domain="[('partner_id','=', company_partner_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    # bank_id = fields.Many2one(
    #     'res.bank', related='bank_account_id.bank_id', readonly=False)
    
        # ACCOUNTS

    property_account_subscription_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Cuenta de Acciones",
                                                       domain="[('internal_type', '=', 'asset_receivable'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Esta cuenta será usada para registrar los saldos de subscripción del accionista, cuenta que puede ser modificada en el partner",
                                                       required=True)
    property_account_shareholding_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Cuenta de Capital Suscripto",
                                                       domain="[('internal_type', '=', 'equity'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Esta cuenta será usada para las para registrar las acciones en una cuenta de capital, a pesar que sea establecida una cuenta por defecto diferente en el partner",
                                                       required=True)
    property_account_integration_id = fields.Many2one('account.account', company_dependent=True,
                                                      string="Cuenta de Capital Integrado",
                                                      domain="[('internal_type', '=', 'equity'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                      help="Esta cuenta será usada para las para registrar las acciones en una cuenta de capital, a pesar que sea establecida una cuenta por defecto diferente en el partner",
                                                      required=True)
    property_account_contribution_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Cuenta de Aportes",
                                                       domain="[('internal_type', '=', 'contribution'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Esta cuenta será usada para las para registrar los partes pendientes de aprobación, a pesar que sea establecida una cuenta por defecto diferente",
                                                       required=True)
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
                                                         string="Descuentos de Emisión",
                                                         domain="[('internal_type', '=', 'equity_issue_discount'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                         help="Esta cuenta será usada para las para registrar los pagos de aportes, a pesar que sea establecida una cuenta por defecto diferente",
                                                         required=True)
    property_account_issue_premium_id = fields.Many2one('account.account', company_dependent=True,
                                                        string="Primas de Emisión",
                                                        domain="[('internal_type', '=', 'equity_issue_premium'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                        help="Esta cuenta será usada para las para registrar las primas de emision de acciones, a pesar que sea establecida una cuenta por defecto diferente",
                                                        required=True)
    
    account_capital_adjustment = fields.Many2one('account.account', company_dependent=True,
                                                 string="Ajuste al capital",
                                                 domain="[('internal_type', '=', 'equity_adjustment'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                 help="Esta cuenta será usada para las para registrar los ajustes de capital, a pesar que sea establecida una cuenta por defecto diferente",
                                                 required=True)

    account_shareholders_for_redemption_of_shares = fields.Many2one('account.account', company_dependent=True,
                                                                    string="Accionistas por rescates de acciones",
                                                                    domain="[('internal_type', '=', 'liability_payable_redemption_shares'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                                    help="Esta cuenta será usada para las para registrar los pagos de aportes, a pesar que sea establecida una cuenta por defecto diferente",
                                                                    required=True, )

    # """Campos usados para la emision y gestion de los bonos"""

    account_cert_payable = fields.Many2one('account.account', company_dependent=True,
                                           string="Cuenta Bonos a pagar",
                                           domain="[('internal_type', '=', 'payable_negociable_obligations'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                           help="Cuenta de Pasivo para registrar las emisiones de obligaciones negociables",
                                           required=True, config_parameter='higher_authority.account_cert_payable')
    account_receivable_cert=fields.Many2one('account.account', company_dependent=True,
                                           string="Créditos por bonos",
                                           domain="[('internal_type', '=', 'asset_receivable'),('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                           help="Cuenta para registrar el saldo pendiente que eel tenedor de bonos debe abonar",
                                           required=True )