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
    # _name = "account.move.line"
    _inherit = "account.move.line"

    suscription_order_id = fields.Many2one(
        'suscription.order', 'Suscription Order', readonly=True)

    integration_line_id = fields.Many2one(
        'integration.order.line', 'Integration Order Line', ondelete='set null', index='btree_not_null')
    integration_order_id = fields.Many2one(
        'integration.order', 'Integration Order', related='integration_line_id.order_id', readonly=True)
    contribution_order_id = fields.Many2one(
        'irrevocable.contribution', 'Contribution Order', readonly=True)
    # portfolio shares
    redemption_order_id = fields.Many2one(
        'share.sale', 'Redemption Order', readonly=True)
    # share_sale
    share_sale_order_id = fields.Many2one(
        'share.sale', 'Share Sale Order', readonly=True)
    # capital reduction
    reduction_order_id = fields.Many2one(
        'capital.reduction', 'Reduction Order', readonly=True)
    # Account Share Cost
    account_share_cost_line_id = fields.Many2one(
        'account.share.cost.line', 'Share Cost Line', ondelete='set null', index='btree_not_null')
    account_share_cost_order_id = fields.Many2one(
        'account.share.cost', 'Share Cost', related='account_share_cost_line_id.order_id', readonly=True)
    # Certificates
    certificate_order_id = fields.Many2one(
        'account.certificate', 'Cert.', related='certificate_line_id.cert_order', readonly=True)
    certificate_line_id = fields.Many2one(
        'account.certificate.line', 'Lineas de Certificados', ondelete='set null', index='btree_not_null')
    certificate_refund_id = fields.Many2one(
        'account.certificate', 'Cert Refund', related='move_id.certificate_refund_id', readonly=True)

    def _copy_data_extend_business_fields(self, values):
        # OVERRIDE to copy the 'purchase_line_id' field as well.
        super(AccountMoveLine, self)._copy_data_extend_business_fields(values)
        values['suscription_order_id'] = self.certificate_line_id.id
        values['integration_line_id'] = self.integration_line_id.id
        values['contribution_order_id'] = self.contribution_order_id.id
        values['redemption_order_id'] = self.redemption_order_id.id
        values['share_sale_order_id'] = self.share_sale_order_id.id
        values['account_share_cost_line_id'] = self.account_share_cost_line_id.id
        values['certificate_line_id'] = self.certificate_line_id.id
        values['certificate_refund_id'] = self.certificate_refund_id.id