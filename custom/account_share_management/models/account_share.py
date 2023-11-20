# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError

from odoo.tools.translate import _

from datetime import timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api


class AccountShare(models.Model):
    _name = 'account.share'
    _description = 'Objeto Accion'
    _order = 'short_name desc'
    _rec_name = 'short_name'

    name = fields.Char(string='Nombre', required=True, tracking=True)
    short_name = fields.Char(string='Referencia', default='New',
                             required=True, copy=False, readonly=True)
    active = fields.Boolean(string='Activo', default=True)

    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('suscribed', 'Suscripto'),
        ('integrated', 'Integrado'),
        ('portfolio', 'En Cartera'),
        ('negotiation', 'En Negociación'),
        ('canceled', 'Cancelado')
    ], help='Defina el estado de la acción', default='draft')

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
    partner_id = fields.Many2one(
        string='Accionista', comodel_name='res.partner', store=True, index=True)

    # valores y cotizacion

    nominal_value = fields.Float(
        string='Valor de Emisión', required=True, copy=True)
    price = fields.Float(string='Valor pactado en la suscripción',
                         help='El el valor al cual se vendió la accion, el monto total que pago el accionista por adquirir la acción', readonly=True, copy=True, compute='_compute_price')
    adjusted_value = fields.Monetary(string='Valor Ajustado', readonly=True,
                                     default=0.0, help='Valor obtenido a partir de una hoja de ajuste')


    issue_premium = fields.Float(
        string='Prima de emision', help='Cotizacion sobre la par', compute='_compute_price')

    issue_discount = fields.Float(
        string='Descuento de Emisión', help='Descuento bajo la par', compute='_compute_price')

    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company.id)

    share_issuance = fields.Many2one(
        string='Orden de Emisión', readonly=True, index=True, store=True, comodel_name='shares.issuance')
    
    user_id = fields.Many2one('res.users', string='Usuario',
                              index=True, tracking=True, default=lambda self: self.env.user)

    
    notes = fields.Html(string='Notas')

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
            if share.state in ['suscribed', 'integrated', 'portfolio', 'negotiation']:
                share.state = 'canceled'
                share.date_of_cancellation = fields.Date.today()
            else:
                raise UserError('No puede cancelarse esta acción')

    def action_portfolio(self):
        for share in self:
            if share.state in ['suscribed', 'integrated']:
                share.update({
                    'state': 'portfolio',
                    'date_of_redemption': fields.Date.today(),
                    'partner_id': False
                })
            else:
                raise UserError('Acción no válida para esta accion')

    def _action_cancel_premium(self):
        for share in self:
            if share.state in ['suscribed', 'integrated']:
                debit_line = {
                    'account_id': self.partner_id.property_account_issue_premium_id or self.company_id.property_account_issue_premium_id or self.env['account.account'].search([
                        ('internal_type', '=', 'equity_issue_premium')])[0],
                    'debit': self.issue_premium,
                    'name':'Anulación Prima %s de Acción nro'%(self.short_name),
                }
                credit_line = {
                    'account_id': self.company_id.financial_year_result_account or self.env['account.account'].search([
                        ('internal_type', '=', 'equity_unaffected')])[0],
                    'credit': self.issue_premium,
                    'name':'Cargo a resultados %s de Acción nro'%(self.short_name),
                }

                cancelation_vals = {
                    'ref': self.date_of_issue or '',
                    'move_type': 'issue_premium_cancelation',
                    'narration': self.notes,
                    'currency_id': self.company_id.currency_id.id,
                    'invoice_user_id': self.user_id and self.user_id.id or self.env.user.id,
                    'partner_id': self.partner_id.id,
                    'invoice_origin': f"Cancelación de Prima: {self.short_name}",
                    'line_ids': [],
                    'company_id': self.company_id.id,
                }
                cancelation_vals['line_ids'].extend(
                    (0, 0, debit_line), (0, 0, credit_line))

                SusMoves = self.env['account.move']
                AccountMove = self.env['account.move'].with_context(
                    default_move_type='issue_premium_cancelation')
                redMove = AccountMove.with_company(
                    cancelation_vals['company_id']).create(cancelation_vals)
                SusMoves |= redMove
                
                share.update({
                'issue_premium': 0.0
                })
            else:
                raise UserError('Acción no válida para esta accion')

    def share_integrate_redemption(self):
        for share in self:
            if share.state in ['negotiation']:
                share.state = 'integrated'
                share.date_of_integration = fields.Datetime.now()
            else:
                raise UserError(
                    'La accion ya ha sido emitida o aun no esta \n autorizado para ello')

    def share_negotiation(self):
        for share in self:
            if share.state in ['portfolio']:
                share.state = 'negotiation'
            else:
                raise UserError(
                    'La accion ya ha sido emitida o aun no esta \n autorizado para ello')
    # low level methods

    @api.model
    def create(self, vals):
        if vals.get('short_name', _('New')) == _('New'):
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'account.share') or _('New')
        res = super(AccountShare, self.create(vals))
        return res

class Partner(models.Model):
    _inherit = 'res.partner'

    shares=fields.One2many(string='Acciones',help='Acciones que posee el accionista', comodel_name='account.share',     inverse_name='partner_id', readonly=True)
