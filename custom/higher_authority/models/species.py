# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError

from odoo.tools.translate import _

from datetime import timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api

from odoo.exceptions import ValidationError


class Species(models.Model):
    _name = 'species'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'ss'
    _order = 'short_name desc'
    _rec_name = 'short_name'

    name = fields.Char('Nombre', required=True,
                       index=True, copy=False, default='New')
    short_name = fields.Char(string='Referencia', required=True, index=True)

    partner_id = fields.One2many(string='Terceros', comodel_name='res.partner', inverse_name='specie_id',
                                 help='campo tecnico usado para asociar estos dos registros')
