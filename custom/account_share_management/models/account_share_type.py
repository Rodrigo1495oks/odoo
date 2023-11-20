# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tools.translate import _

from odoo import models, fields, api


class AccountShareType(models.Model):
    _name = 'account.share.type'
    # _inherits = {'account.asset', 'ref_name'}
    _description = 'Objeto Tipo de acción'
    _order = 'short_name desc'
    _rec_name = 'short_name'

    @api.depends('type')
    def _compute_number_of_votes(self):
        for type in self:
            if type.type=='A':
                type.number_of_votes=5
            elif type.type=='B':
                type.number_of_votes=4
            elif type.type=='C':
                type.number_of_votes=3
            elif type.type=='D':
                type.number_of_votes=1
            elif type.type=='E':
                type.number_of_votes=1

    type=fields.Selection(string='Clase de Acción', help='Eliga el tipo de acción establecido en el estatuto', selection=[
        ('A','Clase A - 5 Votos'),
        ('B','Clase B - 4 Votos'),
        ('C','Clase C - 3 Votos'),
        ('D','Clase D - 1 Voto'),
        ('E','Clase E - 1 Voto'),
    ])
    name = fields.Char(string='Nombre')
    short_name = fields.Char(string='Referencia', default='New',
                             required=True, copy=False, readonly=True)
    active = fields.Boolean(string='Activo', default=True)

    share_ids = fields.One2many(string='Acciones agrupadas',
                                comodel_name='account.share', inverse_name='share_type', readonly=True)

    number_of_votes = fields.Integer(
        string='Cantidad de Votos', required=False, default=1, compute='_compute_number_of_votes', readonly=True)


    # low level methods
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'account.share.issuance') or 'New'
        res = super(AccountShareType, self.create(vals))
        return res