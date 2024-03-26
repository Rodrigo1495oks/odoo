# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from functools import lru_cache
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from odoo.osv import expression
from odoo.tools.float_utils import float_is_zero, float_compare
from odoo import models, fields, api, tools, _
from odoo.osv.expression import get_unaccent_wrapper
from odoo.exceptions import ValidationError
from odoo.addons.base.models.res_partner import _tz_get
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError

class SuscriptionOrderStage(models.Model):
    _name = 'account.suscription.order.stage'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'State of Share Subscription'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'

    name=fields.Char(string='Name')
    short_name = fields.Char(string='Reference',
                             default='New',
            required=True, 
            copy=False, 
            readonly=True)
    fold=fields.Boolean(string='Fold')
    order_state=fields.Selection(string='Order State', selection=[
        ('draft','Draft'), # se permite modificaciones
        ('new','New'), # se cierran las modificaciones
        ('approved','Approved'), # se vuelven a permitir algunas modficaciones, relacionadas a las lineas, para hacer coincidir con price_total
        ('subscribed','Subscribed'), # se bloquea la edicion de nuevo
        ('finished','Finished'), # se bloquea la edicion totalmente
        ('canceled','Canceled'), # se bloquea la edicion totalmente, pero se permite volver a borrador
        ], help='Order State for Suscription Order',default='draft')

    # low level methods

    @api.model
    def create(self, vals):
        if vals.get('short_name', _('New')) == _('New'):
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'account.suscription.order.stage') or _('New')
        return super().create(vals)