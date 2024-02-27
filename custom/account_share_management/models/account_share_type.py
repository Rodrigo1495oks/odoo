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

    def name_get(self):
        result = []
        for ast in self:
            name = '%s - (%s)' % (ast.name, ast.short_name)
            result.append((ast.id, name))
        return result
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
            else:
                type.number_of_votes = 1

    type=fields.Selection(string='Clase de Acción', help='Eliga el tipo de acción establecido en el estatuto', selection=[
        ('A','Clase A - 5 Votos'),
        ('B','Clase B - 4 Votos'),
        ('C','Clase C - 3 Votos'),
        ('D','Clase D - 1 Voto'),
        ('E','Clase E - 1 Voto'),
    ], default='D')
    name = fields.Char(string='Nombre')
    short_name = fields.Char(string='Referencia', default=lambda self: _('New'),index='trigram',
                             required=True, copy=False, readonly=True)
    active = fields.Boolean(string='Activo', default=True)

    share_ids = fields.One2many(string='Acciones agrupadas',
                                comodel_name='account.share', inverse_name='share_type', readonly=True)

    number_of_votes = fields.Integer(
        string='Cantidad de Votos', required=False, default=1, compute='_compute_number_of_votes', readonly=True, store=True)


    # low level methods
    @api.model
    def create(self, vals):
        if vals.get('short_name', _("New")) == _("New"):
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'account.share.type') or _('New')
        return super().create(vals)