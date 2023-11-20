# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo import models, fields, api, tools
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError, ValidationError


class SharesIssuance(models.Model):
    _name = 'account.share.issuance'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Objeto Reunión de asamblea'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'

    def _compute_currency_rate(self):
        for share in self:
            share.currency_rate = self.env['res.currency']._get_conversion_rate(
                share.company_id.currency_id, share.currency_id, share.company_id, share.date_share)

    @api.depends('nominal_value', 'price')
    # busca en el modelo relacionado e l campo precio total
    def _compute_price(self):
        # calcula la prima o el desuento de emision en caso de corresponder
        # presupuesto/pedido de compra
        currency = self.currency_id or self.env.company.currency_id
        for issuance in self:
            nom_price = issuance.nominal_value
            price = issuance.price
            if nom_price > price:
                issuance.update({  # actualizo loscampos de este modelo
                    'issue_discount': currency.round(nom_price-price),
                    'issue_premium': 0
                })
            if nom_price < price:
                issuance.update({  # actualizo loscampos de este modelo
                    'issue_discount': 0,
                    'issue_premium': currency.round(price-nom_price)
                })

    short_name = fields.Char(string='Referencia', default='New',
                             required=True, copy=False, readonly=True)

    name = fields.Char(string='Nombre', )

    makeup_date = fields.Datetime(string='Fecha de Confección', readonly=True,
                                  help='Fecha en que se ha creado esta orden, a partir del topico aprobado correspondiente')
    date_of_issue = fields.Datetime(
        string='Fecha de Emisión', help='Fecha en que se ha ejecutado esta orden y creado las acciones')
    # campos relacionales

    # campos para crear las acciones

    share_type = fields.Many2one(
        string='Grupo de acciones', comodel_name='account.share.type', ondelete='restrict')

    votes_num = fields.Integer(string='Número de Votos',
                               related='share_type.number_of_votes', store=True)  # puede modificarse en la accion mientras sea "editable"

    partner_id = fields.Many2one(
        string='Accionista', comodel_name='res.partner', store=True, index=True)

    # valores y cotizacion
    shares_qty = fields.Integer(
        string='Cantidad', default=0, required=True, help='Cantidad de acciones a emitir')

    nominal_value = fields.Float(
        string='Valor de Emisión', required=True, copy=True)

    price = fields.Float(string='Valor de mercado',
                         help='El el valor al cual se vendió la accion, el monto total que pago el accionista por adquirir la acción', readonly=True, copy=True, compute='_compute_price')

    issue_premium = fields.Float(
        string='Prima de emision', help='Cotizacion sobre la par', compute='_compute_price', readonly=True)

    issue_discount = fields.Float(
        string='Descuento de Emisión', help='Descuento bajo la par', compute='_compute_price', readonly=True)

    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company.id, readonly=True)
    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('approved', 'Aprobado'),
        ('suscribed', 'Suscrito')
        ('cancel', 'Cancelado')
    ], default='draft')

    share_type = fields.Many2one(
        string='Grupo de acciones', comodel_name='account.share.type', ondelete='restrict')
    shares = fields.One2many(string='Acciones a emitir', help='Acciones creadas',
                             comodel_name='account.share', inverse_name='share_issuance', index=True)
    suscription_order = fields.Many2one(
        string='Suscripción', help='Suscripcion de acciones creada', comodel_name='suscription.order', index=True)
    integration_order = fields.Many2one(
        string='Integración', help='Integración de acciones creada', comodel_name='integration.order', index=True)
    share_cost = fields.One2many(
        string='Costos de Emisión', comodel_name='account.share.cost', inverse_name='share_issuance', readonly=True)
    topic = fields.Many2one(string='Tema de Reunión',
                            comodel_name='assembly.meeting.topic', ondelete='restrict')

    irrevocable_contribution = fields.Many2one(
        string='Aporte Irrevocable', comodel_name='irrevocable.contribution', index=True, copy=True, readonly=True)

    # def action_set_canceled(self):
    #     self.ensure_one()
    #     for issue in self:
    #         if issue.state != 'cancel' and issue.state != 'suscribed':
    #             issue.state = 'cancel'
    #             return True
    #         else:
    #             raise UserError(
    #                 'No puede Cancelarse un inmueble que ya esta cancelado o vendido')

    def action_approve(self):
        for issuance in self:
            if issuance.state not in ['draft', 'cancel', 'suscribed', 'approved'] and issuance.topic.id.state == 'approved':
                issuance.state = 'approved'
                # creo las acciones
                for i in self.shares_qty:
                    share_vals = issuance._prepare_share_values()
                    self.env['account.share'].create(share_vals)
                # creo el comprobante de costo de emision
                self._create_share_cost_order()
            else:
                raise UserError('Orden de emision no autorizada')

    def action_cancel(self):
        for issuance in self:
            if issuance.state not in ['draft', 'new', 'suscribed'] and issuance.topic.id.state == 'refused':
                issuance.state = 'cancel'
                for share in issuance.shares:
                    share.share_cancel()

    def action_suscribe(self):
        for issuance in self:
            if issuance.state == 'approved' and not issuance.irrevocable_contribution:
                issuance.state == 'suscribed'
                for share in issuance.shares:
                    share.share_aprove()
            else:
                raise UserError('No ha sido aprobada. O se trata de un aporte irrevocable, en cuyo caso deberá integrar las acciones directamente')

    def action_integrate(self):
        for issuance in self:
            if issuance.state == 'suscribed' or issuance.irrevocable_contribution.state=='approved':
                issuance.state == 'integrated'
                for share in issuance.shares:
                    share.state='integrated'
            else:
                raise UserError('Acción no válida. LA emision no esta suscrita o el aporte irrevocable no esta Aprobado')

    def action_confirm(self):
        self.ensure_one()
        for issue in self:
            if issue.state == 'draft':
                issue.state = 'new'
                # topic_vals = self._prepare_topic_values()
                # self.env['assembly.meeting.topic'].create(topic_vals)
                return True
            else:
                raise UserError(
                    'Accion no permitida')

    def action_draft(self):
        self.ensure_one()
        for issue in self:
            if issue.state != 'draft':
                if issue.state == 'new':
                    issue.state = 'draft'
                    return True
                else:
                    raise UserError(
                        'No se puede cambiar a borrador un fichero que ya esta en marcha')
            else:
                raise UserError(
                    'Accion no permitida')
    # methods

    def _prepare_topic_values(self):
        self.ensure_one()
        vals = {
            "name": f" Emisión N°: {self.short_name}/= {self.makeup_date} ",
            "description": f'Emisión de acciones',
            "topic_type": "issuance",
            "share_issuance": self.id
        }
        return vals

    def _prepare_share_values(self):
        self.ensure_one()
        res = {
            'state': 'draft',
            'date_of_issue': self.date_of_issue,
            'share_type': self.share_type.id,
            'votes_num': self.votes_num,
            'partner_id': self.partner_id.id,
            'nominal_value': self.nominal_value,
            'price': self.price,
            'issue_premium': self.issue_premium,
            'issue_discount': self.issue_discount,
            'share_issuance': self.id,
            # 'suscription_order': self.suscription_order.id,
        }
        return res

    def _create_share_cost_order(self):
        self.ensure_one()
        vals = {
            'int_date': self.date_of_issue,
            'company_id': self.company_id,
            'origin': self.short_name,
            'partner_ref': f"(Partner: {self.partner_id.partner_id.name} : {self.short_name})",
            'date_order': fields.date.today()
        }

        share_cost_order = self.env['account.share.cost'].create(vals)

        self.share_cost = share_cost_order.id

    # low level methods
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'account.share.issuance') or 'New'
        res = super(SharesIssuance, self.create(vals))
        return res
