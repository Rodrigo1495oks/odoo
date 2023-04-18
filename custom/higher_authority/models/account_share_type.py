# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError

from odoo.tools.translate import _

from datetime import timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api

from odoo.exceptions import ValidationError


class AccountShareType(models.Model):
    _name = 'account.share.type'
    # _inherits = {'account.asset', 'ref_name'}
    _description = 'Objeto Tipo de acción'
    _order = 'short_name desc'
    _rec_name = 'short_name'


    name = fields.Char(string='Nombre')
    short_name = fields.Char(string='Referencia', required=True, index=True)
    active = fields.Boolean(string='Activo', default=True)

    share_ids = fields.One2many(string='Acciones agrupadas',
                                comodel_name='account.share', inverse_name='share_type')
    journal_id = fields.Many2one('account.journal', string='Diario Contable', required=True, readonly=False,
                                 check_company=True, domain="[]")
    account_share_id = fields.Many2one('account.account', string='Cuenta de capital',
                                        index=True, ondelete="cascade",
                                        domain="[('deprecated', '=', False), ('company_id', '=', 'company_id'),('is_off_balance', '=', False), ('user_type_id.name',='Equity'))]",
                                        check_company=True,
                                        tracking=True, help='Cuenta contable por defecto, a ser utilizada para las subscripciones de acciones')
    account_asset_id = fields.Many2one('account.account', string='Cuenta de Activo',
                                        index=True, ondelete="cascade",
                                        domain="[('deprecated', '=', False), ('company_id', '=', 'company_id'),('is_off_balance', '=', False), ('user_type_id.name',='Equity'))]",
                                        check_company=True,
                                        tracking=True, help='Cuenta contable por defecto, a ser utilizada para contabilizar la subscripcion en el activo')
    number_of_votes = fields.Integer(
        string='Cantidad de Votos', required=True, default=1)
