# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError

from odoo.tools.translate import _

from datetime import timedelta

from odoo import models, fields, api

from odoo.exceptions import ValidationError


class EstatePropertyType(models.Model):
    _name = 'estate.property.type'
    # _inherits = {'account.asset', 'ref_name'}
    _description = 'Tipo de Propiedad'
    _order = 'name desc'
    _rec_name = 'short_name'

    # calculos / compute fields

    @api.depends('offers_id')
    def _compute_offers(self):
        for type in self:
            # offers = type.mapped('offers_id')
            # type.offers_id = offers
            type.offer_count = len(type.offers_id)

    short_name = fields.Char(string='Nombre Corto',
                             required=True, index=True, size=10)

    name = fields.Char(string='Nombre del tipo de inmueble',
                       size=32, required=True)
    active = fields.Boolean(string='Activo?: ', default=True)

    property_ids = fields.One2many(string='Propiedades', comodel_name='estate.property',
                                   inverse_name='type', help='Propiedades asociadas al tipo')
    sequence = fields.Integer('Secuencia', default=1,
                              help="Used to order stages. Lower is better.")

    offers_id = fields.One2many(string='Ofertas', comodel_name='estate.property.offer', help='Ofertas asociadas al tipo',
                                inverse_name='property_type_id', readonly=True, copy=False)
    offer_count = fields.Integer(
        string='Número de Ofertas', compute='_compute_offers', copy=False, default=10, store=True)
    _sql_constraints = [
        ('unique_name', 'UNIQUE(short_name)',
         'El nombre corto del tipo debe ser unico')
    ]

    def action_view_offers(self, offers=False):
        """This function returns an action that display existing offers of
        given types ids. When only one found, show the offer
        immediately.
        """
        offers_id=None
        if not offers:
            # offers_id may be filtered depending on the user. To ensure we get all
            # offers related to the type, we read them in sudo to fill the
            # cache.
            self.sudo()._read(['offers_id'])
            offers_id = self.offers_id

        result = self.env['ir.actions.act_window']._for_xml_id(
            'bienes.action_offer_in_property_type')
        # choose the view_mode accordingly
        if len(offers_id) > 1:
            result['domain'] = [('id', 'in', offers_id.ids)]
        elif len(offers_id) == 1:
            res = self.env.ref('bienes.estate_property_offer_view_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in result:
                result['views'] = form_view + \
                    [(state, view)
                     for state, view in result['views'] if view != 'form']
            else:
                result['views'] = form_view
            result['res_id'] = offers_id.id
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result
