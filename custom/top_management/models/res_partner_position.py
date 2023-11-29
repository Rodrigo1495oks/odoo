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

    position=fields.Many2one(string='Cargo', comodel_name='res.partner.position', help='Cargo del Accionista dentro de la Compañía')
    

class ResPartnerPosition(models.Model):
    _name='res.partner.position'
    _description='Cargo del Accionista dentro de la Compañía'
    _order = 'name'
    _rec_name = 'name'

    name=fields.Char(string='Nombre del Cargo')
    type=fields.Selection(string='Tipo', selection=[
        ('shareholder','Accionista'),
        ('director','Director'),
        ('receiver','Síndico'),
    ], help='Rol del partner dentro de la companía')
    description=fields.Text(string='Descripción', help='Descripción General del Puesto')
    # Campos relacionales

    partner_id=fields.One2many(string='Accionista', comodel_name='res.partner',inverse_name='position', help='Accionistas', readonly=True)


