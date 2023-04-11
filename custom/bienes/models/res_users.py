# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError

from odoo.tools.translate import _

from datetime import timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api

from odoo.exceptions import ValidationError

class Users(models.Model):
    _inherit='res.users'

    property_ids=fields.One2many(string='Propiedades', comodel_name='estate.property', inverse_name='user_id', help='Propiedades del usuario', copy=False, domain=[('availability','=','True')])


