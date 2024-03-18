# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = ['res.config.settings']
    company_id=fields.Many2one(string='Compañía', comodel_name='res.company', default=lambda self: self.env.company)

    quorum_ext=fields.Float(string='Quórum R. Ext.', help='Fije el Porcentaje de Asistencia para asambleas extraordinarias', related='company_id.quorum_ext', readonly=False, groups='top_management.top_management_group_manager')
    quorum_ord=fields.Float(string='Quórum R. Ord.', help='Fije el Porcentaje de Asistencia para asambleas ordinarias', related='company_id.quorum_ord', readonly=False, groups='top_management.top_management_group_manager')

    group_release_dates=fields.Boolean(string='Administrar Fechas de Revisión',
                                       group='top_management.top_management_group_user', implied_group='top_management.top_management_group_user_release')
    module_note = fields.Boolean("Install Notes app")