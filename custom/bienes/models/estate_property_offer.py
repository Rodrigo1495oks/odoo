# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta
from odoo.tools.float_utils import float_is_zero, float_compare
from odoo.exceptions import UserError

from odoo.tools.translate import _
from datetime import timedelta

from odoo import models, fields, api

from odoo.exceptions import ValidationError


class EstatePropertyOffer(models.Model):
    _name = 'estate.property.offer'
    # _inherits = {'account.asset', 'ref_name'}
    _description = 'Ofertas de Propiedad'
    _order = 'name desc, price desc'
    _rec_name = 'short_name'

    @api.depends('create_date', 'validity')
    def _compute_date_deadline(self):
        for offer in self:
            if offer.create_date and offer.validity > 0:
                units = offer.validity
                offer.date_deadline = fields.Datetime.from_string(
                    offer.create_date)+relativedelta(days=units)

    def _inverse_create_date(self):
        for offer in self:
            if offer.date_deadline and offer.validity > 0:
                units = offer.validity
                offer.create_date = fields.Datetime.from_string(
                    offer.date_deadline)-relativedelta(days=units)

    @api.depends('create_date', 'date_deadline')
    def _compute_is_ongoing(self):
        now = fields.Datetime.now()
        for estate in self:
            estate.is_ongoing = estate.create_date <= now < estate.date_deadline

    @api.depends('property_id.type')
    def _compute_property_type(self):
        """Esta funcion retona el valor por defecto del tipo de propiedad establecido en la propiedad, para rellena el campo tipo
            de propiedad en las ofertas.
        """
        for offer in self:
            offer.property_type_id = offer.property_id.type
    # por defecto los campos computados no se pueden buscar porque no estan guardados en la
    # base de datos. por lo tanto, habrá que definir el criterio o dominio de busqueda mediante una funcion
    # y el atributo search en el campo computado correspondiente

    def _search_is_ongoing(self, operator, value):
        if operator not in ['=', '!=']:
            raise ValueError(_('This operator is not supported'))
        if not isinstance(value, bool):
            raise ValueError(
                _('Value should be True or False (not %s)'), value)
        now = fields.Datetime.now()
        if (operator == '=' and value) or (operator == '!=' and not value):
            domain = [('create_date', '<=', now), ('date_deadline', '>', now)]
        else:
            domain = ['|', ('create_date', '>', now),
                      ('date_deadline', '<=', now)]
        offers_id = self.env['estate.property.offer']._search(domain)
        return [('id', 'in', offers_id)]

    # acciones
    def action_confirm(self):
        for estate_offer in self:
            if estate_offer.status in ['new'] and estate_offer.partner_id:
                property = estate_offer.property_id
                if property.state != 'accept' and property.state == 'offer':
                    estate_offer.status = 'accepted'
                    property.state = 'accept'
                    property.buyer = estate_offer.partner_id
                    property.expected_price = estate_offer.price
                    estate_offer.is_ongoing = True

                    # acepto una oferta y rechazo las demás
                    property.offers_id.filtered(
                        lambda offer: offer.status != 'accepted').action_refuse()

                else:
                    raise UserError(
                        'El inmueble ya se negocio o aún no se ha ofertado')
            else:
                raise UserError('El estado no es el adecuado')
    # campos básicos

    def action_refuse(self):
        for estate_offer in self:
            if estate_offer.status in ['new']:
                estate_offer.status = 'refused'
            else:
                raise UserError('El estado no es el adecuado')

    is_ongoing = fields.Boolean(string="En Realización", default=False, help="La oferta se esta negociando actualmente",
                                compute="_compute_is_ongoing", search='_search_is_ongoing', readonly=True)
    create_date = fields.Datetime(string='Fecha de Creación', default=fields.Date.today(), readonly=False
                                  )
    test_number = fields.Integer(string='Número de prueba', default=0.0)
    short_name = fields.Char(string='Nombre Corto',
                             required=True, index=True, size=10)

    name = fields.Char(string='Nombre del tipo de inmueble',
                       size=32, required=True)
    active = fields.Boolean(string='Activo?: ', default=True)

    price = fields.Float(string='Precio del Inmueble')
    status = fields.Selection(string="Estado", copy=False, selection=[
        ('new', 'Nuevo'),
        ('accepted', 'Aceptado'),
        ('refused', 'Rechazado')
    ], readonly=True, default='new')
    partner_id = fields.Many2one(
        string="Comprador", comodel_name='res.partner', required=True, ondelete="restrict")
    property_id = fields.Many2one(
        string="Propiedad", comodel_name="estate.property", required=True, ondelete="restrict")

    validity = fields.Integer(string='Dias de validez oferta', default=7)

    date_deadline = fields.Datetime(
        string='Fecha de Caducidad', compute="_compute_date_deadline", inverse="_inverse_create_date")

    property_type_id = fields.Many2one(
        string='Tipo de propiedad', comodel_name='estate.property.type', required=False, ondelete="restrict", index=True, copy=False, store=True, compute='_compute_property_type', readonly=True)

    _sql_constraints = [
        ('positive_price', 'CHECK(price>=0)',
         'El precio de la oferta debe ser positivo')
    ]

    # python constraints

    @api.constrains('date_deadline', 'create_date')
    def _check_date_end(self):
        for offer in self:
            if offer.date_deadline <= offer['create_date']:
                raise ValidationError(
                    "La fecha de finalizacion no puede ser anterior a la fecha de creacion de la oferta")
            # all records passed the test, don't return anything
