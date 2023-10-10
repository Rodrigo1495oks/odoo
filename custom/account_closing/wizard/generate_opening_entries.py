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
            fy.fiscal_year=fy.env['account.fiscal.year'].search([('state','=','closed')], limit=1) if not fy.fiscal_year else False
            self.search()

    fiscal_year = fields.Many2one(
        string='Año Fiscal', comodel_name='account.fiscal.year', help='Seleccione el año fiscal a cerrar', required=True, domain=[('state','=','closed')])
    end_journal = fields.Many2one(
        string='Diario de Cierre', comodel_name='account.journal',domain=[('type','=','end_of_year')])

    entry_name = fields.Char(string='Nombre de Entrada Contable', required=True)
    new_fy = fields.Many2one(string='Nuevo Año Fiscal',
                             comodel_name='account.fiscal.year')
    period = fields.Many2one(
        string='Período de Entrada contable', comodel_name='account.fiscal.period', required=True)

    # aCCIONES

    def _create_close_entries(self):
        closing_move_values={
            'ref': self.entry_name or '',
            'move_type': 'year_closing_entry',
            'narration': "Cierre Periodo %s" % (self.fiscal_year.year),
            'invoice_user_id': self.env.user.id,
            'invoice_origin': self.name,
            'invoice_payment_term_id': self.payment_term_id.id,
            'line_ids': [],
            'company_id': self.company_id.id,
        }
    def action_create_closing(self):

        moves = self._create_close_entries() # cambiar

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