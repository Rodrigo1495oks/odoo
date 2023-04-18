# -*- coding: utf-8 -*-
from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date, formatLang


class AccountPayment(models.Model):
    _name = "account.payment"
    _inherit= "account.payment"

    # damos soporte a la funcion de integracion
    partner_type = fields.Selection([
        ('customer', 'Customer'),
        ('supplier', 'Vendor'),
        ('shareholder', 'Shareholder')
    ], default='customer', tracking=True, required=True)


    shareholder_id=fields.Many2one(string='Accionista', comodel_name='account.shareholder')

    @api.depends('journal_id', 'partner_id', 'partner_type', 'is_internal_transfer', 'destination_journal_id')
    def _compute_destination_account_id(self):
        self.destination_account_id = False
        for pay in self:
            if pay.is_internal_transfer:
                pay.destination_account_id = pay.destination_journal_id.company_id.transfer_account_id
            elif pay.partner_type == 'customer':
                # Receive money from invoice or send money to refund it.
                if pay.partner_id:
                    pay.destination_account_id = pay.partner_id.with_company(
                        pay.company_id).property_account_receivable_id
                else:
                    pay.destination_account_id = self.env['account.account'].search([
                        ('company_id', '=', pay.company_id.id),
                        ('account_type', '=', 'asset_receivable'),
                        ('deprecated', '=', False),
                    ], limit=1)
            elif pay.partner_type == 'shareholder':
                # Receive money from invoice or send money to refund it.
                if pay.shareholder_id:
                    pay.destination_account_id = pay.shareholder_id.with_company(
                        pay.company_id).property_account_shareholder_receivable_id
                else:
                    pay.destination_account_id = self.env['account.account'].search([
                        ('company_id', '=', pay.company_id.id),
                        ('account_type', '=', 'asset_receivable'),
                        ('deprecated', '=', False),
                    ], limit=1)
            elif pay.partner_type == 'supplier':
                # Send money to pay a bill or receive money to refund it.
                if pay.partner_id:
                    pay.destination_account_id = pay.partner_id.with_company(
                        pay.company_id).property_account_payable_id
                else:
                    pay.destination_account_id = self.env['account.account'].search([
                        ('company_id', '=', pay.company_id.id),
                        ('account_type', '=', 'liability_payable'),
                        ('deprecated', '=', False),
                    ], limit=1)