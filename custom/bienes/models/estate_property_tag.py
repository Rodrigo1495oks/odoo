# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError

from odoo.tools.translate import _

from datetime import timedelta

from odoo import models, fields, api

from odoo.exceptions import ValidationError


class EstatePropertyTag(models.Model):
    _name = 'estate.property.tag'
    # _inherits = {'account.asset', 'ref_name'}
    _description = 'Etiqueta de Propiedad'
    _order = 'name desc'
    _rec_name = 'short_name'

    short_name = fields.Char(string='Nombre Corto', required=True, index=True, size=10)

    name = fields.Char(string='Nombre etiqueta de inmueble', size=32, required=True)
    active = fields.Boolean(string='Activo?: ', default=True)
    color=fields.Integer(string='Color')
    
    _sql_constraints=[
        ('unique_name','UNIQUE(short_name)','El nombre corto de la etiqueta debe ser unico')
    ]