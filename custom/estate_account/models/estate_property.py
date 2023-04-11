# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError

from odoo.tools.translate import _

from datetime import timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api

from odoo.exceptions import ValidationError, AccessError


class EstateProperty(models.Model):
    _inherit = 'estate.property'

    company_id = fields.Many2one('res.company', 'Company', required=True,
                                 index=True, default=lambda self: self.env.company, readonly=True)
    qty_to_invoice = fields.Integer(
        string='Cantidad a facturar', default=1, required=True, readonly=True)

    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a sales order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()
        journal = self.env['account.move'].with_context(
            default_move_type='out_invoice')._get_default_journal()
        if not journal:
            raise UserError(_('Please define an accounting sales journal for the company %s (%s).') % (
                self.company_id.name, self.company_id.id))

        invoice_vals = {
            'ref': self.short_name or '',
            'move_type': 'out_invoice',
            # 'narration': self.note,
            # 'currency_id': self.pricelist_id.currency_id.id,
            # 'campaign_id': self.campaign_id.id,
            # 'medium_id': self.medium_id.id,
            # 'source_id': self.source_id.id,
            'user_id': self.user_id.id,
            'invoice_user_id': self.user_id.id,
            # 'team_id': self.team_id.id,
            'partner_id': self.buyer.id,
            # 'partner_shipping_id': self.partner_shipping_id.id,
            # 'fiscal_position_id': (self.fiscal_position_id or self.fiscal_position_id.get_fiscal_position(self.partner_invoice_id.id)).id,
            'partner_bank_id': self.company_id.partner_id.bank_ids[:1].id,
            'journal_id': journal.id,  # company comes from the journal
            # 'invoice_origin': self.name,
            # 'invoice_payment_term_id': self.payment_term_id.id,
            # 'payment_reference': self.reference,
            # 'transaction_ids': [(6, 0, self.transaction_ids.ids)],
            'invoice_line_ids': [],
            'company_id': self.company_id.id,
        }
        return invoice_vals

    def _prepare_invoice_line(self, **optional_values):
        """
        Prepare the dict of values to create the new invoice line for a sales order line.

        :param qty: float quantity to invoice
        :param optional_values: any parameter that should be added to the returned invoice line
        """
        self.ensure_one()
        res = {
            # 'display_type': self.display_type,
            # 'sequence': self.sequence,
            'name': self.name,
            # 'product_id': self.product_id.id,
            # 'product_uom_id': self.product_uom.id,
            'quantity': self.qty_to_invoice,
            # 'discount': self.discount,
            'price_unit': self.expected_price,
            # 'tax_ids': [(6, 0, self.tax_id.ids)],
            # 'analytic_account_id': self.order_id.analytic_account_id.id,
            # 'analytic_tag_ids': [(6, 0, self.analytic_tag_ids.ids)],
            # 'sale_line_ids': [(4, self.id)],
        }
        if optional_values:
            res.update(optional_values)

        return res

    def _create_invoices(self):
        """
        Create the invoice associated to the property.
        :param grouped: if True, invoices are grouped by property id. If False, invoices are grouped by
                        (partner_invoice_id, currency)
        :param final: if True, refunds will be generated if necessary
        :returns: list of created invoices
        """
        if not self.env['account.move'].check_access_rights('create', False):
            try:
                self.check_access_rights('write')
                self.check_access_rule('write')
            except AccessError:
                return self.env['account.move']

        # 1) Create invoices.
        invoice_vals_list = []
        invoice_line_vals = []

        # colocamos y vinculamos cada linea de factura con la factura correspondiente

        for property in self:
            property = property.with_company(property.company_id)
            current_section_vals = None
            # down_payments = order.env['sale.order.line']
            invoice_vals = property._prepare_invoice()

            invoiceable_lines = None
            property_line = property._prepare_invoice_line()

            administrative_line = property._prepare_invoice_line(
                name='Gastos Administrativos', price_unit=100)

            invoice_line_vals.append(property_line)
            invoice_line_vals.append(administrative_line)

            invoice_vals['invoice_line_ids'] += invoice_line_vals
            invoice_vals_list.append(invoice_vals)

        # 2) Manage 'grouped' parameter: group by (partner_id, currency_id). no lo hago aca

        # 3) Create invoices.

        # self.env['account.move'].create(invoice_vals)

        # Manage the creation of invoices in sudo because a salesperson must be able to generate an invoice from a
        # sale order without "billing" access rights. However, he should not be able to create an invoice from scratch.
        # moves = self.env['account.move'].sudo().with_context(
        #     default_move_type='out_invoice').create(invoice_vals_list)

        return self.env['account.move'].create(invoice_vals)

    def action_set_sold(self):
        """Esta funcion extiende la funcionalidad de esta accion al vender la propiedad de modo que al ejecutarla se crea una nueva factura"""
        res = super(EstateProperty, self).action_set_sold()

        self._create_invoices()

        return res
