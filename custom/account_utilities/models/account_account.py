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
        # Activos
        ("asset_investments", "Inversiones"),
        ("asset_exchange_realty", "Bienes de Cambio"),
        ("asset_permanents_holdings", "Participaciones Permanentes"),
        ("asset_intangibles", "Activos Intangibles"),
        ("asset_receivable_others", "Otros Créditos"),
        ("asset_others", "Otros Activos"),
        # Pasivos
        ('liability_payable_dividends_redemption_shares','Accionistas - Rescate de Acciones'),
        ('liability_payable_dividends','Dividendos'),
        ('liability_payable_financial_amortized','Obligaciones Amortizadas'),
        ("liability_payable_financial", "Deudas Financieras"),
        ("liability_payable_work", "Remuneraciones y Cargas Sociales"),
        ("liability_payable_fiscal", "Cargas Fiscales"),
        ("liability_payable_advance", "Anticipos de Clientes"),
        ("liability_payable_others", "Otros Pasivos"),

        # Patrimonio Neto
        ('equity_adjustment','Ajuste al Capital'),
        ('contribution','Aportes no Capitalizados'),
        ('contribution_credits','Saldos pendientes Aportes'),
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
        ('expense_financial','Intereses y Componentes Financieros Implicitos'),
        ('expense_secundary','Otros Egresos'),
        ("expense_disposition", "Egresos por Disposición de Activos y/o Cancelación de pasivos"),
        ("expense_extra", "Egresos Extraordinarios"),
    ], ondelete = {
        'asset_investments':  lambda recs: recs.write({'account_type': 'asset_current' }), 
        'asset_exchange_realty':  lambda recs: recs.write({'account_type': 'asset_current' }), 
        'asset_permanents_holdings':  lambda recs: recs.write({'account_type': 'asset_current' }), 
        'asset_intangibles':  lambda recs: recs.write({'account_type': 'asset_current' }), 
        'asset_receivable_others':  lambda recs: recs.write({'account_type': 'asset_current' }),
        'asset_others':  lambda recs: recs.write({'account_type': 'asset_current' }), 
        'liability_payable_dividends_redemption_shares':  lambda recs: recs.write({'account_type': 'liability_payable' }), 'liability_payable_dividends':  lambda recs: recs.write({'account_type': 'liability_payable' }), 'liability_payable_financial_amortized':  lambda recs: recs.write({'account_type': 'liability_payable' }), 'liability_payable_financial':  lambda recs: recs.write({'account_type': 'liability_payable' }),'liability_payable_work':  lambda recs: recs.write({'account_type': 'asset_current' }),'liability_payable_advance':  lambda recs: recs.write({'account_type': 'liability_payable' }),'liability_payable_others':  lambda recs: recs.write({'account_type': 'liability_payable' }),'liability_payable_fiscal':  lambda recs: recs.write({'account_type': 'liability_payable' }),'equity_adjustment':  lambda recs: recs.write({'account_type': 'equity' }),'contribution':  lambda recs: recs.write({'account_type': 'equity' }),'contribution_credits':  lambda recs: recs.write({'account_type': 'equity' }),'contribution_losses':  lambda recs: recs.write({'account_type': 'equity' }),'equity_issue_premium':  lambda recs: recs.write({'account_type': 'equity' }),'equity_issue_discount':  lambda recs: recs.write({'account_type': 'equity' }),'equity_portfolio_shares':  lambda recs: recs.write({'account_type': 'equity' }),'legal_reserve':  lambda recs: recs.write({'account_type': 'equity' }),'reserve':  lambda recs: recs.write({'account_type': 'equity' }),'deferred_results_conv':  lambda recs: recs.write({'account_type': 'equity' }),'deferred_results_deriv':  lambda recs: recs.write({'account_type': 'equity' }),'income_relief':  lambda recs: recs.write({'account_type': 'income' }),'income_refund':  lambda recs: recs.write({'account_type': 'income' }),'income_agricultural':  lambda recs: recs.write({'account_type': 'income' }),'income_valuation':  lambda recs: recs.write({'account_type': 'income' }),'income_investments':  lambda recs: recs.write({'account_type': 'income' }),'income_financial':  lambda recs: recs.write({'account_type': 'income' }),'income_capital':  lambda recs: recs.write({'account_type': 'income' }),'income_disposition':  lambda recs: recs.write({'account_type': 'income' }),'income_extra':  lambda recs: recs.write({'account_type': 'income' }),'expense_agricultural':  lambda recs: recs.write({'account_type': 'expense' }),'expense_valuation':  lambda recs: recs.write({'account_type': 'expense' }),'expense_marketing':  lambda recs: recs.write({'account_type': 'expense' }),'expense_administration':  lambda recs: recs.write({'account_type': 'expense' }),'expense_other':  lambda recs: recs.write({'account_type': 'expense' }),'expense_investments':  lambda recs: recs.write({'account_type': 'expense' }),'expense_financial':  lambda recs: recs.write({'account_type': 'expense' }),'expense_secundary':  lambda recs: recs.write({'account_type': 'expense' }),'expense_disposition':  lambda recs: recs.write({'account_type': 'expense' }),'expense_extra':  lambda recs: recs.write({'account_type': 'expense' })})