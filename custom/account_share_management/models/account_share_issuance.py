# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo import models, fields, api, tools
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError, ValidationError


class SharesIssuance(models.Model):
    _name = 'account.share.issuance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Objeto Orden de Emisión de Acciones'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'
    
    @api.depends('shares.nominal_value')
    def _amount_all(self):
        for issuance in self:
            shares = issuance.shares.filtered(lambda x: x.share_issuance.id==self.id)
            issuance.total_nominal = sum(shares.mapped('nominal_value'))
            issuance.total_prime = sum(shares.mapped('issue_premium'))
            issuance.total_discount = sum(shares.mapped('issue_discount'))
            issuance.total = issuance.total_nominal + issuance.total_prime - issuance.total_discount

    @api.depends('nominal_value', 'price')
    # busca en el modelo relacionado e l campo precio total
    def _compute_price(self):
        # calcula la prima o el desuento de emision en caso de corresponder
        # presupuesto/pedido de compra
        currency = self.env.company.currency_id
        for issuance in self:
            
            nom_price = issuance.nominal_value
            if nom_price > issuance.price:
                issuance.update({  # actualizo los campos de este modelo
                    'issue_discount': currency.round(nom_price-issuance.price),
                    'issue_premium': 0,
                })
            if nom_price < issuance.price:
                issuance.update({  # actualizo loscampos de este modelo
                    'issue_discount': 0,
                    'issue_premium': currency.round(issuance.price-nom_price),
                })

    short_name = fields.Char(string='Referencia', 
                             default=lambda self: _('New'), 
                             index='trigram',
                             required=True, 
                             copy=False, 
                             readonly=True)

    name = fields.Char(string='Título', )

    makeup_date = fields.Date(string='Fecha de Confección', 
                                  readonly=True,default=fields.Date.today(),
                                  help='Fecha en que se ha creado esta orden, a partir del topico aprobado correspondiente')
    date_of_issue = fields.Date(
        string='Fecha de Emisión', required=True,
        help='Fecha en que se ha ejecutado esta orden y creado las acciones')

    # campos para crear las acciones


    votes_num = fields.Integer(string='Número de Votos',
                               related='share_type.number_of_votes', 
                               store=True)  # puede modificarse en la accion mientras sea "editable"

    partner_id = fields.Many2one(
        string='Accionista', 
        required=True,
        comodel_name='res.partner', 
        store=True, 
        index=True)

    # valores y cotizacion
    shares_qty = fields.Integer(
        string='Cantidad', 
        default=0, 
        required=True, 
        help='Cantidad de acciones a emitir')

    nominal_value = fields.Float(
        string='Valor de Emisión', 
        required=True, 
        copy=True, 
        store=True,
        readonly=True,
        default=lambda self: self.env.company.share_price )

    price = fields.Float(string='Valor de mercado',
                         help='El el valor al cual se vendió la accion, el monto total que pago el accionista por adquirir la acción',
                         readonly=False, 
                         required=True,
                         copy=True,)


    issue_premium = fields.Float(
        string='Prima de emision', 
        help='Cotizacion sobre la par', 
        compute='_compute_price', 
        readonly=True)

    issue_discount = fields.Float(
        string='Descuento de Emisión', 
        help='Descuento bajo la par', 
        compute='_compute_price', 
        readonly=True)

                                 
    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('approved', 'Aprobado'),
        ('suscribed', 'Suscrito'),
        ('cancel', 'Cancelado')
    ], default='draft')

    # campos relacionales
    company_id = fields.Many2one('res.company', 'Company', 
    required=True, 
    index=True,
    default=lambda self: self.env.company.id, readonly=True)

    share_type = fields.Many2one(
        string='Grupo de acciones',
        comodel_name='account.share.type',
        ondelete='restrict', required=True)
    shares=fields.One2many(string='Acciones',
                           comodel_name='account.share',
                           readonly=True,
                           help='Acciones Emitidas',
                           inverse_name='share_issuance')
    notes = fields.Html(string='Terms and Conditions')

    # totales

    total_nominal=fields.Float(string='Total Nominal',
                               
                               store=True, readonly=True, 
                               compute='_amount_all')
    total_prime=fields.Float(string='Total Prima',
                               
                               store=True, readonly=True, 
                               compute='_amount_all')
    total_discount=fields.Float(string='Total Discount',
                                
                               store=True, readonly=True, 
                               compute='_amount_all')
    total=fields.Float(string='Total ',
                               
                               store=True, readonly=True, 
                               compute='_amount_all')
    def action_approve(self):
        for issuance in self:
            if issuance.state not in ['draft', 'cancel', 'suscribed', 'approved']: # and issuance.topic.id.state == 'approved':
                issuance.state = 'approved'
                # creo las acciones
                for i in range(self.shares_qty):
                    share_vals = issuance._prepare_share_values()
                    self.env['account.share'].create(share_vals)
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
            if issuance.state == 'approved':
                issuance.state == 'suscribed'
                for share in issuance.shares:
                    share.share_aprove()
            else:
                raise UserError('No ha sido aprobada. O se trata de un aporte irrevocable, en cuyo caso deberá integrar las acciones directamente')

    def action_integrate(self):
        for issuance in self:
            if issuance.state == 'suscribed':
                issuance.state == 'integrated'
                for share in issuance.shares:
                    share.state='integrated'
            else:
                raise UserError('Acción no válida. La emision no esta suscrita o el aporte irrevocable no esta Aprobado')

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
            'name':'Acción %s (de %s)'%(self.share_type.name, self.partner_id.name ), 
            'date_of_issue': self.date_of_issue,
            'share_type': self.share_type.id,
            'votes_num': self.votes_num,
            'partner_id': self.partner_id.id,
            'nominal_value': self.nominal_value,
            'price': self.price,
            'issue_premium': self.issue_premium,
            'issue_discount': self.issue_discount,
            'share_issuance': self.id,
        }
        return res

    # low level methods
    @api.model
    def create(self, vals):
        if vals.get('short_name', _("New")) == _("New"):
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'account.share.issuance') or 'New'
        return super().create(vals)
