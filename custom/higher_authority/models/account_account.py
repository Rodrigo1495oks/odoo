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
        ('contribution','Aportes no Capitalizados'),
        ('contribution_credits','Saldos pendientes Aportes')
        ('equity_issue_premium','Primas de Emision'),
        ('equity_issue_discount','Descuentos de emision'),
        ('equity_portfolio_shares','Acciones en cartera'),
        ('liability_payable_redemption_shares','Accionistas - Rescate de Acciones'),
        ('liability_payable_amortized','Obligaciones Amortizadas'),
        ('certificate_refund','Reintegro de Bonos'),
        ('certificate','Bono'),
        ('certificate_line','Lineas de Bono'),
        ('other_expenses','Otros Gastos'),
        ('expenses_interest_and_implicit_financial_components','Intereses y Componentes Financieros Implicitos'),
    ])