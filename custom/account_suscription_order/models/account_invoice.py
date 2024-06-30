# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import time

from odoo import api, fields, models, Command, _

_logger = logging.getLogger(__name__)

TOLERANCE = 0.02  # tolerance applied to the total when searching for a matching purchase order

class AccountMove(models.Model):
    _inherit = 'account.move'

    suscription_id = fields.Many2one('account.suscription.order', store=False, readonly=True,
        states={'draft': [('readonly', False)]},
        string='Suscription Order',
        help="Auto-complete from a past Suscription order.")

    suscription_order_count = fields.Integer(compute="_compute_suscription_count", string='Suscription Order Count')

    def _get_invoice_reference(self):
        self.ensure_one()
        lines_mapped=self.line_ids.mapped('suscription_cash_line_id.order_id.origin') or self.line_ids.mapped('suscription_cash_line_id.order_id.origin')
        vendor_refs = [ref for ref in set(lines_mapped) if ref]
        if self.ref:
            return [ref for ref in self.ref.split(', ') if ref and ref not in vendor_refs] + vendor_refs
        return vendor_refs

    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_subscription_id(self):
        res = super(AccountMove, self)._onchange_partner_id()
        if self.partner_id and\
                self.move_type in ['suscription'] and\
                self.currency_id != self.partner_id.property_purchase_currency_id and\
                self.partner_id.property_purchase_currency_id.id:
            if not self.env.context.get('default_journal_id'):
                journal_domain = [
                    ('type', '=', 'suscription'),
                    ('company_id', '=', self.company_id.id),
                    ('currency_id', '=', self.partner_id.property_purchase_currency_id.id),
                ]
                default_journal_id = self.env['account.journal'].search(journal_domain, limit=1)
                if default_journal_id:
                    self.journal_id = default_journal_id
            if self.env.context.get('default_currency_id'):
                self.currency_id = self.env.context['default_currency_id']
            if self.partner_id.property_purchase_currency_id:
                self.currency_id = self.partner_id.property_purchase_currency_id
        return res

    @api.depends('line_ids.suscription_cash_line_id')
    def _compute_suscription_count(self):
        for move in self:
            move.suscription_order_count = len(move.line_ids.suscription_cash_line_id.order_id) + len(move.line_ids.suscription_credit_line_id.order_id)+len(move.line_ids.suscription_product_line_id.order_id)

    def action_view_source_suscription_orders(self):
        self.ensure_one()
        source_orders = self.line_ids.suscription_order_id
        result = self.env['ir.actions.act_window']._for_xml_id('account_suscription_order.account_suscription_order_action')
        if len(source_orders) > 1:
            result['domain'] = [('id', 'in', source_orders.ids)]
        elif len(source_orders) == 1:
            result['views'] = [(self.env.ref('account_suscription_order.account_suscription_order_view_form', False).id, 'form')]
            result['res_id'] = source_orders.id
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    @api.model_create_multi
    def create(self, vals_list):
        # OVERRIDE
        moves = super(AccountMove, self).create(vals_list)
        for move in moves:
            if move.reversed_entry_id:
                continue
            subscriptions = move.line_ids.suscription_cash_line_id.order_id | move.line_ids.suscription_credit_line_id.order_id | \
            move.line_ids.suscription_product_line_id.order_id

            if not subscriptions:
                continue
            refs = [subscription._get_html_link() for subscription in subscriptions]
            message = _("This entry has been created from: %s") % ','.join(refs)
            move.message_post(body=message)
        return moves

class AccountMoveLine(models.Model):
    """ Override AccountInvoice_line to add the link to the Suscription order line it is related to"""
    _inherit = 'account.move.line'

    integration_cash_line_id = fields.Many2one(comodel_name= 'account.suscription.cash.line', string='Integration Order Cash Line', ondelete='set null', index='btree_not_null')
    suscription_cash_line_id = fields.Many2one(comodel_name= 'account.suscription.cash.line', string='Suscription Order Cash Line', ondelete='set null', index='btree_not_null')

    integration_credit_line_id = fields.Many2one(comodel_name= 'account.suscription.credit.line', string='Integration Order Credit Line', ondelete='set null', index='btree_not_null')
    suscription_credit_line_id = fields.Many2one(comodel_name= 'account.suscription.credit.line', string='Suscription Order Credit Line', ondelete='set null', index='btree_not_null')

    integration_product_line_id = fields.Many2one(comodel_name= 'account.suscription.product.line', string='Integration Order Credit Line', ondelete='set null', index='btree_not_null')
    suscription_product_line_id = fields.Many2one(comodel_name= 'account.suscription.product.line', string='Suscription Order Credit Line', ondelete='set null', index='btree_not_null')

    suscription_order_id = fields.Many2one(comodel_name= 'account.suscription.order',string= 'Suscription Order', related='suscription_cash_line_id.order_id', readonly=True)


    def _copy_data_extend_business_fields(self, values):
        # OVERRIDE to copy the 'purchase_line_id' field as well.
        super(AccountMoveLine, self)._copy_data_extend_business_fields(values)
        values['suscription_cash_line_id'] = self.suscription_cash_line_id.id
        values['integration_cash_line_id'] = self.integration_cash_line_id.id
        values['suscription_credit_line_id'] = self.suscription_credit_line_id.id
        values['integration_credit_line_id'] = self.integration_credit_line_id.id
        values['suscription_product_line_id'] = self.suscription_product_line_id.id
        values['integration_product_line_id'] = self.integration_product_line_id.id
        values['suscription_order_id'] = self.suscription_order_id.id