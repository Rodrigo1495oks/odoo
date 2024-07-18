# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from functools import lru_cache
from pytz import timezone, UTC
from markupsafe import Markup
from odoo.exceptions import UserError
from datetime import datetime, timedelta, timezone, time
from odoo.tools.float_utils import float_is_zero, float_compare, float_round
from odoo import models, fields, api, tools, _
from odoo.osv.expression import get_unaccent_wrapper
from odoo.exceptions import ValidationError
from odoo.addons.base.models.res_partner import _tz_get
from odoo.tools.misc import get_lang
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, relativedelta, format_amount, format_date, formatLang, get_lang, \
    groupby
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError


class SoCashLine(models.Model):
    _inherit = 'account.suscription.cash.line'

    contribution_id = fields.Many2one(string='Contribution Order', comodel_name='account.irrevocable.contribution',
                                      readonly=True)

    contribution_line_ids = fields.One2many(comodel_name='account.move.line', inverse_name='contribution_cash_line_id',
                                            string="Contribution Lines",
                                            readonly=True, copy=False,
                                            domain=[('move_id.move_type', '=', 'contribution')])

    def has_non_bank_payments(self):
        """
        Devuelve True si al menos un pago asociado con esta línea no es de tipo "bank".
        Laamo a esta funcion cuando procedo a integrar la orden
        :return True, si tiene pagos diferentes a banco o False si todos los pagos asociados son en Transferencia
        Bancaria
        :type bool
        """

        partial_values_list=self._get_all_pay_lines()
        non_bank_payments=[]
        for reconciled_partial in partial_values_list:
            non_bank_payments.append(reconciled_partial['aml_id'])

        non_bank_payments = self.env['account.move.line'].search([
            ('id', 'in', non_bank_payments),
            ('journal_id.type', '!=', 'bank')
        ])
        return bool(non_bank_payments)

    def _get_all_pay_lines(self):
        """ determines the integrated amount of the cash and credit lines"""
        for line in self:
            if not line.display_type:
                # compute qty_invoiced
                amount = 0.0
                reconciled_lines = line._get_subscribed_lines()
                if not reconciled_lines:
                    line.amount_paid = 0.0

                self.env['account.partial.reconcile'].flush_model([
                    'credit_amount_currency', 'credit_move_id', 'debit_amount_currency',
                    'debit_move_id', 'exchange_move_id',
                ])
                query = '''
                            SELECT
                                part.id,
                                part.exchange_move_id,
                                part.debit_amount_currency AS amount,
                                part.credit_move_id AS counterpart_line_id
                            FROM account_partial_reconcile part
                            WHERE part.debit_move_id IN %s

                            UNION ALL

                            SELECT
                                part.id,
                                part.exchange_move_id,
                                part.credit_amount_currency AS amount,
                                part.debit_move_id AS counterpart_line_id
                            FROM account_partial_reconcile part
                            WHERE part.credit_move_id IN %s
                        '''
                self._cr.execute(query, [tuple(reconciled_lines.ids)] * 2)

                partial_values_list = []  # lista de diccionarios de la conciliacion parcial
                counterpart_line_ids = set()  # listado (recordset?) de lineas de pago
                exchange_move_ids = set()  # (no se usa practicamente)
                for values in self._cr.dictfetchall():
                    partial_values_list.append({
                        'aml_id': values['counterpart_line_id'],
                        'partial_id': values['id'],
                        'amount': values['amount'],
                        'currency': self.currency_id,
                    })
                    counterpart_line_ids.add(values['counterpart_line_id'])
                    if values['exchange_move_id']:
                        exchange_move_ids.add(values['exchange_move_id'])

                if exchange_move_ids:
                    self.env['account.move.line'].flush_model(['move_id'])
                    query = '''
                        SELECT
                            part.id,
                            part.credit_move_id AS counterpart_line_id
                        FROM account_partial_reconcile part
                        JOIN account_move_line credit_line ON credit_line.id = part.credit_move_id
                        WHERE credit_line.move_id IN %s AND part.debit_move_id IN %s

                        UNION ALL

                        SELECT
                            part.id,
                            part.debit_move_id AS counterpart_line_id
                        FROM account_partial_reconcile part
                        JOIN account_move_line debit_line ON debit_line.id = part.debit_move_id
                        WHERE debit_line.move_id IN %s AND part.credit_move_id IN %s
                    '''
                    self._cr.execute(query, [tuple(exchange_move_ids), tuple(counterpart_line_ids)] * 2)

                    for values in self._cr.dictfetchall():
                        counterpart_line_ids.add(values['counterpart_line_id'])
                        partial_values_list.append({
                            'aml_id': values['counterpart_line_id'],
                            'partial_id': values['id'],
                            'currency': self.company_id.currency_id,
                        })

                counterpart_lines = {x.id: x for x in self.env['account.move.line'].browse(counterpart_line_ids)}
                for partial_values in partial_values_list:
                    partial_values['aml'] = counterpart_lines[partial_values['aml_id']]
                    partial_values['is_exchange'] = partial_values['aml'].move_id.id in exchange_move_ids
                    if partial_values['is_exchange']:
                        partial_values['amount'] = abs(partial_values['aml'].balance)
                return partial_values_list
