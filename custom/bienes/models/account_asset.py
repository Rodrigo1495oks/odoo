# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError

from odoo.tools.translate import _

from datetime import timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api

from odoo.exceptions import ValidationError


class AccountAsset(models.Model):
    _inherit = "account.asset"

    estate_id = fields.One2many(string='Propiedades Asociadas',
                                comodel_name='estate.property', inverse_name='selection_b')

    asset_type = fields.Selection(string='Tipo de Activo', selection=[
        ('no_type', 'Sin tipo Asignado'),
        ('land', 'Terreno'),
        ('building', 'Construcción'),
        ('truck', 'Camión'),
        ('van', 'Camioneta'),
        ('utilitarian', 'Utilitario'),
        ('facility', 'Instalaciones'),
        ('tools', 'Herramientas'),
        ('tractor', 'Tractor'),
        ('agricultural_tools', 'Herramientas Agrícolas'),
        ('intangible_assets', 'Activos Intagibles')
    ], default='no_type', required=True, help="Selecione la catagoría del rubro Bien de Uso")

    property_state=fields.Selection(string='Situación Contractual', selection=[
        ('own','En Propiedad'),
        ('off','Baja'),
        ('sold','Vendido')
    ],default='own')
    # constrains

    @api.constrains("profile_id")
    def _check_profile_change(self):
        if len(self.estate_id) > 0:
            raise ValidationError(
                _(
                    "No se puede Cambiar la categoría de activo "
                    "con propiedades asociadas."
                )
            )

    @api.constrains('profile_id')
    def _check_asset_type(self):
        type=self.asset_type
        if type and type=='land':
            if self.profile_id and self.profile_id not in ['Terrenos','Campos']:
                raise ValidationError('Si el el tipo de activo fijo es Terreno, la categoria debe ser campos o terrenos')
    
