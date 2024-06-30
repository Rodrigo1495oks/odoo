# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round, float_is_zero, float_compare
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = 'stock.move'

    suscription_line_id = fields.Many2one(
        'account.suscription.product.line', 'Suscription Order Line',
        ondelete='set null', index='btree_not_null', readonly=True)
    created_suscription_line_id = fields.Many2one(
        'account.suscription.product.line', 'Created Suscription Order Line',
        ondelete='set null', index='btree_not_null', readonly=True, copy=False)

    @api.model
    def _prepare_merge_moves_distinct_fields(self):
        distinct_fields = super(StockMove, self)._prepare_merge_moves_distinct_fields()
        distinct_fields += ['suscription_line_id', 'created_suscription_line_id']
        return distinct_fields

    @api.model
    def _prepare_merge_negative_moves_excluded_distinct_fields(self):
        return super()._prepare_merge_negative_moves_excluded_distinct_fields() + ['created_suscription_line_id']

    def _prepare_extra_move_vals(self, qty):
        vals = super(StockMove, self)._prepare_extra_move_vals(qty)
        vals['suscription_line_id'] = self.suscription_line_id.id
        return vals

    def _prepare_move_split_vals(self, uom_qty):
        vals = super(StockMove, self)._prepare_move_split_vals(uom_qty)
        vals['suscription_line_id'] = self.suscription_line_id.id
        return vals

    def _clean_merged(self):
        super(StockMove, self)._clean_merged()
        self.write({'created_suscription_line_id': False})

    def _get_upstream_documents_and_responsibles(self, visited):
        if self.created_suscription_line_id and self.created_suscription_line_id.state not in ('contributed', 'canceled','integrated') \
                and (self.created_suscription_line_id.state != 'draft' or self._context.get('include_draft_documents')):
            return [(self.created_suscription_line_id.order_id, self.created_suscription_line_id.order_id.user_id, visited)]
        elif self.suscription_line_id and self.purchase_line_id.state not in ('contributed', 'canceled','integrated'):
            return[(self.suscription_line_id.order_id, self.suscription_line_id.order_id.user_id, visited)]
        else:
            return super(StockMove, self)._get_upstream_documents_and_responsibles(visited)

    def _get_related_invoices(self):
        """ Overridden to return the suscriptions and integrations related to this stock move.
        """
        rslt = super(StockMove, self)._get_related_invoices()
        rslt += self.mapped('picking_id.suscription_id.suscription_move').filtered(lambda x: x.state == 'posted')
        rslt+=self.mapped('picking_id.suscription_id.integration_move').filtered(lambda x: x.state == 'posted')
        return rslt

    def _get_source_document(self):
        res = super()._get_source_document()
        return self.suscription_line_id.order_id or res

    def _get_all_related_aml(self):
        # The back and for between account_move and account_move_line is necessary to catch the
        # additional lines from a cogs correction
        return super()._get_all_related_aml() | self.suscription_line_id.suscription_line_ids.move_id.line_ids.filtered(
            lambda aml: aml.product_id == self.suscription_line_id.product_id) | self.suscription_line_id.move_lines_ids.move_id.line_ids.filtered(
            lambda aml: aml.product_id == self.suscription_line_id.product_id)

    def _get_all_related_sm(self, product):
        return super()._get_all_related_sm(product) | self.filtered(lambda m: m.suscription_line_id.product_id == product)

    def _get_dest_account(self, accounts_data):
        if self.suscription_line_id:
            """If it is a movement of materials by integration
                then use the forecast contingency for materials by
                integration
            """
            return self.location_dest_id.forecast_integration_account.id or accounts_data['stock_integration_forecast'] or self.env.company.forecast_integration_account.id \
            or self.env['account.account'].search(domain=[('account_type','=','liability_payable_forecast'), ('deprecated', '=', False), ('company_id', '=', self.env.company)], limit=1)
        else:
            return super(StockMove, self)._get_dest_account(accounts_data)

        # la cuenta de la ubicacion del producto o en su defecto la predeterminada establecida en la categoria