# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError

from odoo.tools.translate import _

from datetime import timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api

from odoo.exceptions import ValidationError


class Partner(models.Model):
    _inherit = 'res.partner'

    start_date = fields.Date(
        string='Fecha Inicio del cargo', readonly=False)
    end_date = fields.Date(string='Fecha de Finalización cargo', readonly=False)