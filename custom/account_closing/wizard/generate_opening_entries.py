# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import frozendict


class CreateOpeningEntries(models.TransientModel):
    _name = 'create.opening.entry'
    _description = 'Generar Asientos de cierre'

    # Compute methods
    @api.depends('fiscal_year')
    def _compute_fiscal_year(self):
        """Vinculo un año fiscal por defecto, si es que no lo especifiqué"""
        for fy in self:
            fy.fiscal_year = fy.env['account.fiscal.year'].search(
                [('state', '=', 'open')], limit=1) if not fy.fiscal_year else False

    fiscal_year = fields.Many2one(
        string='Año Fiscal', comodel_name='account.fiscal.year', help='Seleccione el año fiscal a cerrar', required=True, domain=[('state', '=', 'open')])
    end_journal = fields.Many2one(
        string='Diario de Cierre', comodel_name='account.journal', domain=[('type', '=', 'end_of_year')])

    entry_name = fields.Char(
        string='Nombre de Entrada Contable', required=True)
    new_fy = fields.Many2one(string='Nuevo Año Fiscal',
                             comodel_name='account.fiscal.year')
    period = fields.Many2one(
        string='Período de Entrada contable', comodel_name='account.fiscal.period', required=True, domain=[('fiscal_year', '=', 'fiscal_year')])

    # aCCIONES

    def _create_close_entries(self, date):
        closing_move_values = {
            'ref': self.entry_name or '',
            'move_type': 'year_closing_entry',
            'narration': "Cierre Periodo %s" % (self.fiscal_year.year),
            'invoice_user_id': self.env.user.id,
            'invoice_origin': self.entry_name,
            'line_ids': [],
            'company_id': self.env.company.id,
            'fiscal_year': self.id,
            'fiscal_period': self.period.id
        }
        closing_lines_values = {
            'account_id': '',
            'credit': 0,
            'debit': 0,
        }

        # 1. Iterar sobre todas las cuentas de resultados
        inc_a = self.env['account.account'].search([
            ('account_type', 'like', 'income')])
        exp_a = self.env['account.account'].search([
            ('account_type', 'like', 'expense')])
        result_account = self.company_id.financial_year_result_account or self.env['account.account'].search([
            ('internal_type', '=', 'equity_unaffected')])[0]
        result = 0
        for account in inc_a:
            # a leo el saldo de la cuenta
            domain = [('account_id', '=', account.id), ('date', '<=', date)]
            move_lines = self.env['account.move.line'].search(domain)
            balance = 0
            for line in move_lines:
                balance += (line.debit - line.credit)
            balance = -(balance)
            result += balance
            if balance >= 0.0:
                closing_lines_values.update({
                    'account_id': account.id,
                    'debit': balance,
                    'credit': 0,
                })
            closing_move_values['line_ids'].append(
                (0, 0, closing_lines_values))
        for account in exp_a:
            # a leo el saldo de la cuenta
            domain = [('account_id', '=', account.id), ('date', '<=', date)]
            move_lines = self.env['account.move.line'].search(domain)
            balance = 0
            for line in move_lines:
                balance += (line.debit - line.credit)
            balance = -(balance)
            result += balance
            if balance <= 0.0:
                closing_lines_values.update({
                    'account_id': account.id,
                    'debit': 0,
                    'credit': balance,
                })
            closing_move_values['line_ids'].append(
                (0, 0, closing_lines_values))

        # Debito las pérdidas o acredito las ganancia segun corresponda
        if result > 0.0:
            closing_lines_values.update({
                'account_id': result_account.id,
                'debit': 0,
                'credit': result,
            })
        elif result < 0.0:
            closing_lines_values.update({
                'account_id': result_account.id,
                'debit': result,
                'credit': 0,
            })
        # Asigno al año fiscal el monto del resultado
        self.fiscal_year.balance=result
        closing_move_values['line_ids'].append((0, 0, closing_lines_values))
        # 3) Create invoices.
        ClosingMoves = self.env['account.move']
        AccountMove = self.env['account.move'].with_context(
            default_move_type='year_closing_entry')
        closingMove = AccountMove.create(closing_move_values)
        ClosingMoves |= closingMove
        return closingMove

    def action_create_closing(self):
        if self.fiscal_year.state != 'open':
            return {
                'warning': {
                    'title': 'Operación no válida',
                    'message': 'El período fiscal esta cerrado'}
            }
        moves = self._create_close_entries(self.fiscal_year.date_to)  # cambiar
        self.fiscal_year.account_move|=moves

        # cerrar los periodos
        self.fiscal_year.state = 'closed'
        for period in self.fiscal_year.periods:
            period.state = 'closed'

        action = {
            'name': _('Closing Entries Move'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'context': {'create': False},
        }
        if len(moves) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': moves.id,
            })
        else:
            action.update({
                'view_mode': 'tree,form',
                'domain': [('id', 'in', moves.ids)],
            })
        return action