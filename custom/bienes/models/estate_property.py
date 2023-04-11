# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError

from odoo.tools.translate import _

from datetime import timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api

from odoo.exceptions import ValidationError


class EstateProperty(models.Model):
    _name = 'estate.property'
    # _inherits = {'account.asset', 'ref_name'}
    _description = 'Objeto propiedad heredado de Asset'
    _order = 'name desc'
    _rec_name = 'short_name'

    # creamos el campo relacionado para heredar

    # estate_id = fields.Many2one(comodel_name='account.asset', ondelete='cascade', required=True, string='Identificación del Activo',
    #                             help='Campo relacionado al Activo Fijo Creado en la contabilidad [Modulo Asset Management]', index=True, store=True)

    # computos

    def unlink(self):
        # Do some business logic, modify vals...

        # ...
        for estate in self:
            if estate.state not in ['canceled', 'draft']:
                raise UserError(
                    _('No se puede eliminar una propiedad que este en estado:  \'%s\'.') % (estate.state,))
        # Then call super to execute the parent method
        return super().unlink()

    @api.depends('living_area', 'garden_area', 'estate_area')
    def _compute_total_area(self):
        for estate in self:
            estate.total_area = estate.living_area+estate.garden_area+estate.estate_area

    @api.depends('offers_id.price')
    def _compute_best_offer(self):
        maximun_price = 0
        for estate in self:
            if len(estate.offers_id) > 0:
                maximun_price = max(estate.offers_id.mapped('price'))
                estate.best_price = maximun_price
            else:
                estate.best_price = 0

    @api.depends('estate_price', 'building_price')
    def _compute_total_value(self):
        for estate in self:
            estate.total_value = estate.estate_price+estate.building_price

    @api.depends('total_value', 'sell_margin')
    def _compute_selling_price(self):
        for estate in self:
            if estate.total_value and estate.sell_margin > 0:
                estate.selling_price = (
                    1+estate.sell_margin)*estate.total_value
            else:
                estate.selling_price = 0

    # metodos onchange
    @api.onchange('garden')
    def _onchange_garden(self):
        if self.garden:
            self.garden_area = 10
            self.garden_orientation = 'north'
            # opcionalmente, el metodo onchange puede retornar un mensaje
            # este mensaje es solo de ejemplo
            return {'warning': {
                'title': _("Warning"),
                'message': ('Tiene Jardín')}}
        else:
            self.garden_area = 0
            self.garden_orientation = ''

            return {'warning': {
                'title': _("Warning"),
                'message': ('No tiene jardín')}}

    # acciones
    def action_set_sold(self):
        self.ensure_one()
        for estate in self:
            if estate.state != 'sold' and estate.state != 'canceled' and estate.active:
                if estate.state == 'accept':
                    if estate.buyer and estate.selection_b and estate.selection_b.property_state =='own':
                        estate.state = 'sold'
                        estate.selection_b.property_state == 'sold'
                        return True
                    else:
                        raise UserError(
                            'No hay vendedor o activo fijo asignado. Revise ambos campos y la situacion contractual del activo en el módulo de contabilidad')
                else:
                    raise UserError(
                        'Tiene que haber al menos una oferta aceptada para poder vender el inmueble!')
            else:
                raise UserError(
                    'No puede venderse un inmueble que ya esta vendido o cancelado')

    def action_set_canceled(self):
        self.ensure_one()
        for estate in self:
            if estate.state != 'canceled' and estate.state != 'sold' and estate.active:
                estate.state = 'canceled'
                return True
            else:
                raise UserError(
                    'No puede Cancelarse un inmueble que ya esta cancelado o vendido')

    def action_confirm(self):
        self.ensure_one()
        for estate in self:
            if estate.state == 'draft' and estate.active:
                estate.state = 'new'
                return True
            else:
                raise UserError(
                    'Accion no permitida')

    def action_draft(self):
        self.ensure_one()
        for estate in self:
            if estate.state != 'draft' and estate.active:
                if estate.state == 'new':
                    estate.state = 'draft'
                    return True
                else:
                    raise UserError(
                        'No se puede cambiar a borrador un fichero que ya estaen marcha')
            else:
                raise UserError(
                    'Accion no permitida')

    def action_offer(self):
        self.ensure_one()
        for estate in self:
            if estate.state != 'draft' and estate.active:
                if estate.state == 'new':
                    if estate.offers_id:
                        estate.state = 'offer'
                        return True
                    else:
                        raise UserError('No hay ofertas recibidas')
                else:
                    raise UserError('La negociacion no admite más ofertas')
            else:
                raise UserError(
                    'Accion no permitida')

    short_name = fields.Char(string='Nombre Corto', required=True, index=True)

    name = fields.Char(string='Nombre del Inmueble', size=10, translate=True)
    building = fields.Boolean(string='Tiene Construcción?: ',
                              help='Determina si hay o no una construcción sobre le terreno')

    active = fields.Boolean(string='Activo?: ', default=True)
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Urgente')], string='Prioridad', default='0', index=True)
    state = fields.Selection(string='Estado del inmueble', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('offer', 'Oferta Recibida'),
        ('accept', 'Oferta Aceptada'),
        ('sold', 'Vendido'),
        ('canceled', 'Cancelado')
    ], default='draft', required=False, help='En que estado se encuentra el inmueble', copy=False, tracking=True, index=True, readonly=True)

    availability = fields.Boolean(string='Disponibilidad')

    destination = fields.Selection(string='Utilidad', help='Escoja si la función del edificio es Coorporativa o Casa Habitación', selection=[
        ('none', 'Ninguna'),
        ('comercial', 'Coorporativo'),
        ('home', 'Casa Habitación')
    ], required=True)

    # building_id = fields.One2many(string='Construcción Relacionada', help='Si el terreno tiene una construcción, deberá elegir de la lista el activo correspondiente', comodel_name='account.asset',inverse_name='estate_property', domain=[
    #                               '|', ('profile_id.name', '=', 'Edificios Comerciales'), ('profile_id.name', '=', 'Casa Habitacion')], context={}, ondelete='restrict', delegate=True)

    # widgets de campos normales

    boolean_toggle = fields.Boolean(string='boolean_toggle')
    description = fields.Text(string='Descripción')
    post_code = fields.Char(string='Código Postal')
    count = fields.Integer(string='Test Count', default=100)
    percentage_pie = fields.Float(string='Porcentaje', default=50)
    money_earned = fields.Float(string='Dinero Ganado', default=10)
    toggle_button = fields.Boolean(string='Toogle')

    # widgets de campos relacionales

    selection_a = fields.Selection(string='radio Selection', selection=[(
        'state_1', 'Estado 1'), ('state_2', 'Estado 2'), ('state_3', 'Estado 3')])
    selection_b = fields.Many2one(string='Activo Fijo', comodel_name='account.asset',
                                  index=True, tracking=True, domain=[('asset_type', '=', 'land')])
    # https://www.youtube.com/watch?v=tpmcTV8K4Mw
    date_reserve = fields.Date(
        string='Fecha de Reservación', required=True, store=True, default=fields.Date.today())

    date_availability = fields.Date(
        string='Fecha de Disponibilidad')

    estate_price = fields.Float(string='Precio del Terreno',
                                readonly=False, copy=False)

    building_price = fields.Float(string='Precio de las construcciones', readonly=False, help='Precio de la Construcción que se encuentra sobre el terreno'
                                  )
    total_value = fields.Float(string='Valor total del inmueble',
                               help="Sumatoria del valor del terreno y el valor de las construcciones sobre él", compute="_compute_total_value")
    sell_margin = fields.Float(string='Margen de Ganancia',
                               help='Indique el coeficiente de ganancia a aplicar sobre el terreno')
    selling_price = fields.Float(string='Precio de Venta', readonly=False, copy=False, compute="_compute_selling_price"
                                 )
    expected_price = fields.Float(
        string='Precio Fijado', readonly=True, default=0.0)

    offices = fields.Integer(string='Número de Oficinas',
                             help='Si el edificio es una oficina comercial, de lo contrario deje este campo vacio')
    bedrooms = fields.Integer(
        string='Cantidad de Habitaciones', help='Cantidad de Habitaciones', default=2)

    living_area = fields.Integer(
        string='Cantidad de Livings', help='Numero de salas de estar')
    facades = fields.Integer(string='Cantidad de Fachadas', help='Número de fachadas'
                             )
    garage = fields.Boolean(string='Tiene Garaje?: ', default=False)
    garden = fields.Boolean(string='Tiene Jardín?: ', default=False)
    floors = fields.Integer(string='Cantidad de Plantas',
                            help='Cantidad de Pisos del edificio o casa habitación')
    garden_area = fields.Integer(string='Area de Jardín')
    estate_area = fields.Float(string='Metros Totales de Superficio del Terreno',
                               help='Rellene con la superfiie del Inmueble unicamente')
    total_area = fields.Integer(
        string='Superficie Total Cubierta en Mts cuadrados', compute="_compute_total_area")
    garden_orientation = fields.Selection(string='Orientación del Jardin', selection=[
        ('none', 'No posee jardín'),
        ('north', 'Norte'),
        ('south', 'Sur'),
        ('east', 'Este'),
        ('west', 'Oeste')
    ], help='Escoja la orientacion del jardín, si la tiene, de lo contrario escoja "no posee jardín"')

    best_price = fields.Float(string="Mejor Oferta",
                              help="Mejor precio de las ofertas", compute="_compute_best_offer")

    # campos relacionales

    type = fields.Many2one(string='Tipo de Propiedad',
                           comodel_name='estate.property.type', index=True, tracking=True)

    user_id = fields.Many2one('res.users', string='Salesperson',
                              index=True, tracking=True, default=lambda self: self.env.user)
    buyer = fields.Many2one(
        string='Comprador', comodel_name='res.partner', index=True, tracking=True, readonly=True)

    tags_ids = fields.Many2many(string='Etiquetas', comodel_name='estate.property.tag', relation='estate_property_tag_rel',
                                column1='estate_id', column2='tag_id', help="Escoje las etiquetas correspondientes", tracking=True)

    offers_id = fields.One2many(
        string="Ofertas", comodel_name="estate.property.offer", inverse_name="property_id")

    _sql_constraints = [
        ('check_margin', 'CHECK(sell_margin >= 0 AND sell_margin <= 1)',
         'El margen de venta debe ser un numero entre 0 y 1.'),
        ('positive_expected_price', 'CHECK(expected_price>=0)',
         'El precio de venta acordado debe ser positivo'),
        ('positive_selling_price', 'CHECK(selling_price>=0)',
         'El precio de venta debe ser positivo'),
        ('building_price', 'CHECK(building_price>=0)',
         'El precio de las construcciones debe ser positivo'),
        ('estate_price', 'CHECK(estate_price>=0)',
         'El precio del inmueble debe ser positivo'),
        ('estate_price', 'CHECK(estate_price>=0)',
         'El precio del inmueble debe ser positivo'),
    ]

    # pyhthon constraints

    @api.constrains('selling_price', 'expected_price')
    def _check_selling_price(self):
        precision = self.env['decimal.precision'].precision_get(
            "Product Unit of Measure")
        for estate in self:
            if not float_is_zero(estate.expected_price, precision_digits=precision):
                if estate.expected_price < (estate.selling_price)*0.90:
                    raise ValidationError(
                        'El precio fijado no puede ser menor al 90 por ciento del precio de la valuacion de la construccion')
                return False
            else:
                return True
