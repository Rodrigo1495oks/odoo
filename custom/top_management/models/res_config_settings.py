# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = ['res.config.settings']
    company_id=fields.Many2one(string='Compañía', comodel_name='res.company', default=lambda self: self.env.company)

    quorum_ext=fields.Float(string='Quórum R. Ext.', help='Fije el Porcentaje de Asistencia para asambleas extraordinarias', related='company_id.quorum_ext', readonly=False)
    quorum_ord=fields.Float(string='Quórum R. Ord.', help='Fije el Porcentaje de Asistencia para asambleas ordinarias', related='company_id.quorum_ord', readonly=False)