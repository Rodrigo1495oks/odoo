# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import frozendict


class CancelOpeningEntries(models.TransientModel):
    _name = 'cancel.opening.entry'
    _description = 'Cancelar Asientos de cierre'

    # Compute methods
    @api.depends('fiscal_year')
    def _compute_fiscal_year(self):
        """Vinculo un año fiscal por defecto, si es que no lo especifiqué"""
        for fy in self:
            fy.fiscal_year = fy.env['account.fiscal.year'].search(
                [('state', '=', 'closed')], limit=1) if not fy.fiscal_year else False
    @api.depends('move_ids')
    def _compute_from_moves(self):
        for record in self:
            
            move_ids = record.move_ids._origin
            record.residual = len(move_ids) == 1 and move_ids.amount_residual or 0
            record.currency_id = len(move_ids.currency_id) == 1 and move_ids.currency_id or False
            record.move_type = move_ids.move_type if len(move_ids) == 1 else (any(move.move_type in ('in_invoice', 'out_invoice') for move in move_ids) and 'some_invoice' or False)
    @api.depends('fiscal_year')
    def _compute_closing_entry(self):
        """Vinculo el asiento de cierre, si lo hay"""
        for closing in self:
            self.move_ids = closing.env['account.move'].search(
                [('move_type', '=', 'year_closing_entry'), ('fiscal_year', '=', 'fiscal_year')])[0] if closing.fiscal_year else False
    date_mode = fields.Selection(selection=[
            ('custom', 'Specific'),
            ('entry', 'Journal Entry Date')])
    fiscal_year = fields.Many2one(
        string='Año Fiscal', comodel_name='account.fiscal.year', help='Seleccione el año fiscal a cerrar', required=True, domain=[('state', '=', 'closed')])
    date = fields.Date(string='Reversal date', default=fields.Date.context_today)
    move_ids = fields.Many2one(string='Cierre Relacionado', comodel_name='account.move', help='Campo técnico para relacionar el asiento de cierre a cancelar', domain=[
                                    ('move_type', '=', 'year_closing_entry')], compute='_compute_closing_entry', readonly=True)
    new_move_ids = fields.Many2many('account.move', 'cancel_opening_entry_new_move', 'reversal_id', 'new_move_id')
    refund_method = fields.Selection(string='Reembolso',selection=[
            ('refund', 'Partial Refund'),
            ('cancel', 'Full Refund'),
            ('modify', 'Full refund and new draft invoice')], default='cancel', readonly=True)
    journal_id=fields.Many2one(
        string='Diario de Cierre', comodel_name='account.journal', domain=[('type', '=', 'end_of_year')])
    reason = fields.Char(string='Reason')

    # computed fields
    residual = fields.Monetary(compute="_compute_from_moves")
    currency_id = fields.Many2one('res.currency', compute="_compute_from_moves")
    move_type = fields.Char(compute="_compute_from_moves")
    # aCCIONes
    def action_cancel_closing(self):
        # cerrar los periodos
        self.fiscal_year.state = 'open'
        for period in self.fiscal_year.periods:
            period.state = 'closed'
        if self.move_ids.state == 'cancel':
            # abro el año y los períodos fiscales
            return {
                'warning': {
                    'title': 'Asiento Cancelado',
                    'message': 'El Asiento ya ha sido cancelado. el estado de el año y periodo fiscal a sido establecido a abierto'}
            }
        self.reverse_moves()
        
    def _prepare_default_reversal(self, move):
        reverse_date = self.date if self.date_mode == 'custom' else move.date
        return {
            'ref': _('Reversal of: %(move_name)s, %(reason)s', move_name=move.name, reason=self.reason)
                   if self.reason
                   else _('Reversal of: %s', move.name),
            'date': reverse_date,
            'invoice_date_due': reverse_date,
            'invoice_date': move.is_invoice(include_receipts=True) and (self.date or move.date) or False,
            'journal_id': self.journal_id.id,
            'invoice_payment_term_id': None,
            'invoice_user_id': move.invoice_user_id.id,
            'auto_post': 'at_date' if reverse_date > fields.Date.context_today(self) else 'no',
        }

    def reverse_moves(self):
        self.ensure_one()
        moves = self.move_ids

        # Create default values.
        default_values_list = []
        for move in moves:
            default_values_list.append(self._prepare_default_reversal(move))
        
        batches = [
            [self.env['account.move'], [], True],   # Moves to be cancelled by the reverses.
            [self.env['account.move'], [], False],  # Others.
        ]
        for move, default_vals in zip(moves, default_values_list):
            is_auto_post = default_vals.get('auto_post') != 'no'
            is_cancel_needed = not is_auto_post and self.refund_method in ('cancel', 'modify')
            batch_index = 0 if is_cancel_needed else 1
            batches[batch_index][0] |= move
            batches[batch_index][1].append(default_vals)

        # Handle reverse method.
        moves_to_redirect = self.env['account.move']
        for moves, default_values_list, is_cancel_needed in batches:
            new_moves = moves._reverse_moves(default_values_list, cancel=is_cancel_needed)

            if self.refund_method == 'modify':
                moves_vals_list = []
                for move in moves.with_context(include_business_fields=True):
                    moves_vals_list.append(move.copy_data({'date': self.date if self.date_mode == 'custom' else move.date})[0])
                new_moves = self.env['account.move'].create(moves_vals_list)

            moves_to_redirect |= new_moves

        self.new_move_ids = moves_to_redirect

        # Create action.
        action = {
            'name': _('Reverse Moves'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
        }
        if len(moves_to_redirect) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': moves_to_redirect.id,
                'context': {'default_move_type':  moves_to_redirect.move_type},
            })
        else:
            action.update({
                'view_mode': 'tree,form',
                'domain': [('id', 'in', moves_to_redirect.ids)],
            })
            if len(set(moves_to_redirect.mapped('move_type'))) == 1:
                action['context'] = {'default_move_type':  moves_to_redirect.mapped('move_type').pop()}
        return action