# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from bisect import bisect_left
from collections import defaultdict
import re



class AccountAccount(models.Model):
    _name = "account.account"
    _inherit = ['account.account']

    account_type=fields.Selection(selection_add=[
        ('liability_payable_redemption_shares','Accionistas - Rescate de Acciones'),
        ('liability_payable_amortized','Obligaciones Amortizadas'),
        ('certificate_refund','Reintegro de Bonos'),
        ('certificate','Bono'),
        ('certificate_line','Lineas de Bono'),
        # Patrimonio Neto
        ('equity_adjustment','Ajuste al Capital'),
        ('contribution','Aportes no Capitalizados'),
        ('contribution_credits','Saldos pendientes Aportes')
        ('contribution_losses','Aportes para Absorber Pérdidas'),
        ('equity_issue_premium','Primas de Emision'),
        ('equity_issue_discount','Descuentos de emision'),
        ('equity_portfolio_shares','Acciones en cartera'),
        ('legal_reserve','Reserva Legal'),
        ('reserve','Reserva'),
        ('deferred_results_conv','Resultados Diferidos por Diferencias de Conversión'),
        ('deferred_results_deriv','Resultados Diferidos por Instrumentos Derivados'),
        # Ingresos
        ("income_relief", "Ingreso por Desgravaciones"),
        ("income_refund", "Ingreso Por Reintegros"),
        ("income_agricultural", "Ingreso Por Produción Agropecuaria"),
        ("income_valuation", "Ingresos por Valuaciones"),
        ("income_investments", "Ingresos por inversiones en entes relacionados"),
        ("income_financial", "Ingresos financieros y por tenencia"),
        ("income_capital", "Interés del capital propio"),
        ("income_disposition", "Ingresos por Disposición de Activos y/o Cancelación de pasivos"),
        ("income_extra", "Ingresos Extraordinarios"),
        # Egresos
        ('expense_agricultural','Egresos por producción agropecuaria'),
        ("expense_valuation", "Egresos por Valuaciones"),
        ("expense_marketing", "Gastos de Comercialización"),
        ("expense_administration", "Gastos de Administración"),
        ('expense_other','Otros Gastos'),
        ("expense_investments", "Egresos por inversiones en entes relacionados"),
        ('expenses_interest_and_implicit_financial_components','Intereses y Componentes Financieros Implicitos'),
        ('expense_secundary','Otros Egresos'),
        ("expense_disposition", "Egresos por Disposición de Activos y/o Cancelación de pasivos"),
        ("expense_extra", "Egresos Extraordinarios"),
    ])