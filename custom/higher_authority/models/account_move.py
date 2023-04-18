import ast
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta
from functools import lru_cache

from odoo import api, fields, models, Command, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import frozendict, formatLang, format_date, float_compare, Query
from odoo.tools.sql import create_index
from odoo.addons.web.controllers.utils import clean_action

from odoo.addons.account.models.account_move import MAX_HASH_VERSION


class AccountMoveLine(models.Model):
    _name = "account.move.line"
    _inherit = "account.move.line"

    move_type = fields.Selection(
        selection=[
            ('entry', 'Journal Entry'),
            ('suscription','suscription'),
            ('integration','Integration'),
            ('out_invoice', 'Customer Invoice'),
            ('out_refund', 'Customer Credit Note'),
            ('in_invoice', 'Vendor Bill'),
            ('in_refund', 'Vendor Credit Note'),
            ('out_receipt', 'Sales Receipt'),
            ('in_receipt', 'Purchase Receipt'),
        ],
        string='Type',
        required=True,
        readonly=True,
        tracking=True,
        change_default=True,
        index=True,
        default="entry",
    )
    shareholder_id = fields.Many2one(
        'account.shareholder',
        string='Accionista',
        readonly=True,
        tracking=True,
        states={'draft': [('readonly', False)]},
        check_company=True,
        change_default=True,
        ondelete='restrict',
    )

    integration_orders = fields.One2many(string='Orden de Integración', comodel_name='integration.order', inverse_name='suscription_order',
                                         help='Campo técnico usado para relacionar la orden de suscripcion ocn la de integracion respectiva')

    def is_suscription_document(self, include_receipts=False):
        return self.move_type in ['suscription']
    def is_integration_document(self, include_receipts=False):
        return self.move_type in ['integration']
    
    def _search_default_journal(self):
        if self.payment_id and self.payment_id.journal_id:
            return self.payment_id.journal_id
        if self.statement_line_id and self.statement_line_id.journal_id:
            return self.statement_line_id.journal_id
        if self.statement_line_ids.statement_id.journal_id:
            return self.statement_line_ids.statement_id.journal_id[:1]

        if self.is_sale_document(include_receipts=True):
            journal_types = ['sale']
        elif self.is_purchase_document(include_receipts=True):
            journal_types = ['purchase']
        elif self.payment_id or self.env.context.get('is_payment'):
            journal_types = ['bank', 'cash']
        elif self.is_integration_document():
            journal_types = ['integration']
        elif self.is_suscription_document():
            journal_types = ['suscription']
        else:
            journal_types = ['general']

        company_id = (self.company_id or self.env.company).id
        domain = [('company_id', '=', company_id), ('type', 'in', journal_types)]

        journal = None
        currency_id = self.currency_id.id or self._context.get('default_currency_id')
        if currency_id and currency_id != self.company_id.currency_id.id:
            currency_domain = domain + [('currency_id', '=', currency_id)]
            journal = self.env['account.journal'].search(currency_domain, limit=1)

        if not journal:
            journal = self.env['account.journal'].search(domain, limit=1)

        if not journal:
            company = self.env['res.company'].browse(company_id)

            error_msg = _(
                "No journal could be found in company %(company_name)s for any of those types: %(journal_types)s",
                company_name=company.display_name,
                journal_types=', '.join(journal_types),
            )
            raise UserError(error_msg)

        return journal
    
    @api.constrains('journal_id', 'move_type')
    def _check_journal_move_type(self):
        for move in self:
            if move.is_purchase_document(include_receipts=True) and move.journal_id.type != 'purchase':
                raise ValidationError(_("Cannot create a purchase document in a non purchase journal"))
            if move.is_sale_document(include_receipts=True) and move.journal_id.type != 'sale':
                raise ValidationError(_("Cannot create a sale document in a non sale journal"))
            elif move.is_integration_document() and move.journal_id.type!='integration':
                raise ValidationError(_("Cannot create a integration document in a non integration journal"))
            elif move.is_suscription_document() and move.journal_id.type!='suscription':
                raise ValidationError(_("Cannot create a suscription document in a non suscription journal"))
            
    # para tomar los datos del accionista y no del partner, para el pago de integracion
    
    @api.depends('partner_id','shareholder_id')
    def _compute_partner_integration(self):
        for move in self:
            if move.move_type=='suscription':
                move.partner_id=move.shareholder_id.partner_id.id
    @api.depends('partner_id','shareholder_id')
    def _compute_invoice_payment_term_id(self):
        for move in self:
            if move.is_sale_document(include_receipts=True) and move.partner_id.property_payment_term_id:
                move.invoice_payment_term_id = move.partner_id.property_payment_term_id
            elif move.is_purchase_document(include_receipts=True) and move.partner_id.property_supplier_payment_term_id:
                move.invoice_payment_term_id = move.partner_id.property_supplier_payment_term_id
            elif move.is_suscription_document(include_receipts=True) and move.partner_id.property_payment_term_id:
                move.invoice_payment_term_id = move.partner_id.property_payment_term_id
            else:
                move.invoice_payment_term_id = False
        # === Partner fields === #
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        readonly=True,
        tracking=True,
        states={'draft': [('readonly', False)]},
        compute='_compute_partner_integration',
        inverse='_inverse_partner_id',
        check_company=True,
        change_default=True,
        ondelete='restrict',
    )

    @api.depends('invoice_payment_term_id', 'invoice_date', 'currency_id', 'amount_total_in_currency_signed', 'invoice_date_due')
    def _compute_needed_terms(self):
        for invoice in self:
            is_draft = invoice.id != invoice._origin.id
            invoice.needed_terms = {}
            invoice.needed_terms_dirty = True
            sign = 1 if invoice.is_inbound(include_receipts=True) else -1
            if (invoice.is_invoice(True) or invoice.is_suscription_document() or invoice.is_integration_document()) and invoice.invoice_line_ids:
                if invoice.invoice_payment_term_id:
                    if is_draft:
                        tax_amount_currency = 0.0
                        untaxed_amount_currency = 0.0
                        for line in invoice.invoice_line_ids:
                            untaxed_amount_currency += line.price_subtotal
                            for tax_result in (line.compute_all_tax or {}).values():
                                tax_amount_currency += -sign * tax_result.get('amount_currency', 0.0)
                        untaxed_amount = untaxed_amount_currency
                        tax_amount = tax_amount_currency
                    else:
                        tax_amount_currency = invoice.amount_tax * sign
                        tax_amount = invoice.amount_tax_signed
                        untaxed_amount_currency = invoice.amount_untaxed * sign
                        untaxed_amount = invoice.amount_untaxed_signed
                    invoice_payment_terms = invoice.invoice_payment_term_id._compute_terms(
                        date_ref=invoice.invoice_date or invoice.date or fields.Date.today(),
                        currency=invoice.currency_id,
                        tax_amount_currency=tax_amount_currency,
                        tax_amount=tax_amount,
                        untaxed_amount_currency=untaxed_amount_currency,
                        untaxed_amount=untaxed_amount,
                        company=invoice.company_id,
                        sign=sign
                    )
                    for term in invoice_payment_terms:
                        key = frozendict({
                            'move_id': invoice.id,
                            'date_maturity': fields.Date.to_date(term.get('date')),
                            'discount_date': term.get('discount_date'),
                            'discount_percentage': term.get('discount_percentage'),
                        })
                        values = {
                            'balance': term['company_amount'],
                            'amount_currency': term['foreign_amount'],
                            'discount_amount_currency': term['discount_amount_currency'] or 0.0,
                            'discount_balance': term['discount_balance'] or 0.0,
                            'discount_date': term['discount_date'],
                            'discount_percentage': term['discount_percentage'],
                        }
                        if key not in invoice.needed_terms:
                            invoice.needed_terms[key] = values
                        else:
                            invoice.needed_terms[key]['balance'] += values['balance']
                            invoice.needed_terms[key]['amount_currency'] += values['amount_currency']
                else:
                    invoice.needed_terms[frozendict({
                        'move_id': invoice.id,
                        'date_maturity': fields.Date.to_date(invoice.invoice_date_due),
                        'discount_date': False,
                        'discount_percentage': 0
                    })] = {
                        'balance': invoice.amount_total_signed,
                        'amount_currency': invoice.amount_total_in_currency_signed,
                    }
    def action_register_suscription_payment(self):
        ''' Open the account.payment.register wizard to pay the selected journal entries.
        :return: An action opening the suscription.payment.register wizard.
        '''
        return {
            'name': _('Register Payment'),
            'res_model': 'suscription.payment.register',
            'view_mode': 'form',
            'context': {
                'active_model': 'account.move',
                'active_ids': self.ids,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }