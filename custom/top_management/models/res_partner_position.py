# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError

from odoo.tools.translate import _

from datetime import timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api

from odoo.exceptions import ValidationError


class ResPartnerPosition(models.Model):
    _name='res.partner.position'
    _description='Cargo del Accionista dentro de la Compañía'
    _order = 'name'
    _rec_name = 'short_name'
    _inherit = ['base.archive']

    name=fields.Char(string='Nombre del Cargo')
    type=fields.Selection(string='Tipo', selection=[
        ('shareholder','Accionista'),
        ('shareholder','Director'),
        ('shareholder','Síndico'),
    ], help='Rol del partner dentro de la companía')
    description=fields.Text(string='Descripción', help='Descripción General del Puesto')