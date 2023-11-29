# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _name = "res.company"
    _inherit = 'res.company'

    quorum_ext=fields.Float(string='Quórum R. Ext.', help='Fije el Porcentaje de Asistencia para asambleas extraordinarias', readonly=False)
    quorum_ord=fields.Float(string='Quórum R. Ord.', help='Fije el Porcentaje de Asistencia para asambleas ordinarias', readonly=False)
