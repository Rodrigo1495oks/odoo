# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError

from odoo.tools.translate import _

from datetime import timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api

from odoo.exceptions import ValidationError


class AccountShare(models.Model):
    _name = 'account.share'
    # _inherits = {'account.asset', 'ref_name'}
    _description = 'Objeto Accion'
    _order = 'short_name desc'
    _rec_name = 'short_name'

    @api.depends('nominal_value', 'price')
    # busca en el modelo relacionado e l campo precio total
    def _compute_price(self):
        # calcula la prima o el desuento de emision en caso de corresponder
        # presupuesto/pedido de compra
        currency = self.currency_id or self.shareholder.property_sharehold_currency_id or self.env.company.currency_id
        for share in self:
            nom_price = share.nominal_value
            price = share.price
            if nom_price > price:
                share.update({  # actualizo loscampos de este modelo
                    'issue_discount': currency.round(nom_price-price),
                    'issue_premium': 0
                })
            if nom_price < price:
                share.update({  # actualizo loscampos de este modelo
                    'issue_discount': 0,
                    'issue_premium': currency.round(price-nom_price)
                })

    name = fields.Char(string='Nombre')
    short_name = fields.Char(string='Referencia', required=True, index=True)
    active = fields.Boolean(string='Activo', default=True)

    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('subscribed', 'Suscripto'),
        # ('integrated', 'Integrado'),
        ('portfolio', 'En Cartera'),
        ('negotiation', 'En Negociación'),
        ('canceled', 'Cancelado')
    ], help='Defina el estado de la acción')

    date_of_issue = fields.Datetime(string='Fecha de Emisión', readonly=True)
    date_of_integration = fields.Datetime(
        string='Fecha de Emisión', readonly=True)
    date_of_cancellation = fields.Datetime(
        string='Fecha de Cancelación', readonly=True)
    date_of_redemption = fields.Datetime(
        string='Fecha de Rescate', readonly=True)

    share_type = fields.Many2one(
        string='Grupo de acciones', comodel_name='account.share.type', ondelete='restrict')

    votes_num = fields.Integer(string='Número de Votos',
                               related='share_type.number_of_votes', store=True)
    shareholder = fields.Many2one(
        string='Accionista', comodel_name='account.shareholder', store=True, index=True)

    # valores y cotizacion

    nominal_value = fields.Float(
        string='Valor de Emisión', required=True, copy=True)
    price = fields.Float(string='Valor pactado en la suscripción',
                         help='El el valor al cual se vendió la accion, el monto total que pago el accionista por adquirir la acción', readonly=True, copy=True, compute='_compute_price')

    issue_premium = fields.Float(
        string='Prima de emision', help='Cotizacion sobre la par', compute='_compute_price')

    issue_discount = fields.Float(
        string='Descuento de Emisión', help='Descuento bajo la par', compute='_compute_price')

    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company.id)

    share_issuance = fields.Many2one(
        string='Orden de Emisión', readonly=True, index=True, store=True, comodel_name='shares.issuance')

    suscription_order = fields.Many2one(
        string='Orden de Subscripción', comodel_name='suscription.order', index=True)

    # def action_integrate(self):
    #     for share in self:
    #         if share.state == 'new' or share.state == 'subscribed':
    #             share.state == 'integrated'
    #             share.date_ofintegration = fields.Datetime.now()
    #         else:
    #             raise UserError(
    #                 'La accion ya ha sido emitida o aun no esta \n autorizado para ello')

    def share_aprove(self):
        for share in self:
            if share.state == 'new':
                share.state = 'subscribed'
                share.date_of_issue = fields.Datetime.now()
            else:
                raise UserError(
                    'La accion ya ha sido emitida o aun no esta \n autorizado para ello')

    def share_cancel(self):
        for share in self:
            share.state='canceled'