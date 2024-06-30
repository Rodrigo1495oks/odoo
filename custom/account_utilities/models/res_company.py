# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _name = "res.company"
    _inherit = 'res.company'

    bussines_name=fields.Char(string='Denominación Social', size=32, required=True)
    start_street=fields.Char(string='Domicilio de Constitucion')
    start_date=fields.Date(string='Inicio de Actividades')
    duration=fields.Integer(string='Duración', help='Duración en Años')
    code_insc=fields.Char(string='Código', help='Código de inscripción Registro Público')