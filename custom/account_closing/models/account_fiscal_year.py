# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime, timedelta, date
import calendar
import re
from dateutil.relativedelta import relativedelta

class AccountFiscalYear(models.Model):
    _name = "account.fiscal.year"
    _inherit = "account.fiscal.year"
    _description = 'Objeto Año Fiscal'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'

    def _get_valid_years(self):
        lst = []
        for year in range(1900, 2030):
            lst.append((f'{year}',year))
        return lst
    
    name = fields.Char(string='Año Fiscal')
    state = fields.Selection(string='Estado', selection=[('closed', 'Cerrado'), ('open', 'Abierto')],
                             help='Indique si el año fiscal esta abierto o cerrado, solo puede haber un año fiscal en curso', default='open', readonly=True)
    year = fields.Selection(string='Año', default='2020', selection=_get_valid_years)
    short_name = fields.Char(string='Referencia', default='New',
                             required=True, copy=False, readonly=True)
    end_journal = fields.Many2one(
        string='Diario de Cierre', comodel_name='account.journal', domain=[('type', '=', 'end_of_year')], help='Seleccione el diario de Cierre')
    periods = fields.One2many(
        string='Periodos', comodel_name='account.fiscal.period', inverse_name='fiscal_year', help='Periodos Fiscales Creados', readonly=True)
    account_move=fields.Many2one(string='Asientos de Cierre', help='Asientos de cierre asociados', comodel_name='account.move', readonly=True)

    balance=fields.Float(string='Saldo del Período', default=0.0, readonly=True, )
    reduction_ids = fields.One2many(
        string='Reducciones', comodel_name='capital.reduction', inverse_name='fiscal_year', readonly=True)

    def name_get(self):
        result = []
        for fy in self:
            name = '%s %s (%s)' % (fy.date_from, ', '.join(
                fy.date_to), ', '.join(fy.year))
            result.append((fy.id, name))
            return result

    @api.constrains('state')
    def _check_state(self):
        for fy in self:
            # Busco todos los años fiscales registrados
            closed_year = self.search([('state', '=', 'open')], limit=1)
            if closed_year:
                raise ValidationError(
                    _(
                        "Ya existe otro período fiscal en curso. \n"
                        "Antes de crear otro debe cerrar el anterior.\n"
                        "'{closed_year}'"
                    ).format(
                        closed_year=closed_year.name
                    ))
    # ACCIONES
    def _prepare_period_values(self, start_date, end_date,):
        self.ensure_one()
        period_vals = {
            'name': f'Período-{start_date.year} °',
            'state': 'open',
            'year': f'{start_date.year}',
            'start_date': f'{start_date.strftime("%d/%m/%Y")}',
            'end_date': f'{end_date.strftime("%d/%m/%Y")}',
            'short_name': f'{start_date.strftime("%B")}/{start_date.year}',
            'op_cl': False,
            'fiscal_year': self.id,
        }
        return period_vals

    def create_monthly_periods(self):
        "los periodos serán siempre anuales (12 meses, 365 dias)"
        for fy in self:
            year = fy.date_from.year
            if fy.state == 'open':
                for i in range(1, 12):
                    day = calendar.monthrange(year=year, month=i)
                    start_date = fields.date(
                        year=year, month=i, day=day[0])
                    end_date = fields.date(year=year, month=i, day=day[1])
                    period_values = fy._prepare_period_values(
                        year, start_date, end_date)
                    period_values['op_cl'] = True if i == 1 or i == 12 else False
                    period_values['name'] = 'Período-%s °%s' % (year, i)
                    new_p = fy.env['account.fiscal.period'].create(
                        period_values)
                    fy.periods += new_p
                    
        return UserWarning('Períodos Mensuales Creados correctamente')

    def create_quaterly_periods(self):
        "los periodos serán siempre anuales (12 meses, 365 dias)"
        for fy in self:
            year = fy.date_from.year
            for i in range(1, 13, 3):
                start_date = datetime.date(year, i, 1)
                end_date = datetime.date(
                    year, i+2, calendar.monthrange(year, i+2)[1])
                period_values = fy._prepare_period_values(
                    year, start_date, end_date)
                period_values['op_cl'] = True if i in [3, 12] else False
                period_values['name'] = 'Período-%s °%s' % (year, i)
                new_p = fy.env['account.fiscal.period'].create(
                    period_values)
                fy.periods += new_p
        return UserWarning('Períodos Mensuales Creados correctamente')
    
    def create_capital_reduction(self):
        'Si el periodo tiene pérdidas, creo la reducción'
        # Si las pérdidas superan el parámetro......
        if self.state=='closed' and not self.reduction_ids:
            total_cap = self.get_capital_value()
            total_reserve = self.get_reserve_value() # no implemente todavia
            if self.balance<0.0:
                if any([self.balance >= 0.0, not abs(self.balance) >= abs(total_cap/2   +total_reserve)]):  # si es perdida
                    return {
                        'warning': {
                            'title': 'Operación no válida',
                            'message': 'La pérdida de este ejercicio no supera el   parametro minimo'}
                    }
                Reduction = self.env['capital.reduction']
                NewReduction = self.env['capital.reduction']
                vals_for_reduction = self._prepare_reduction_values()
                redMove = NewReduction.create(vals_for_reduction)
                self.reduction_ids.append(0, 0, redMove)
                Reduction |= redMove
        else:
            raise UserError('El registro ya tiene una reducción pendiente o se encuentra abierto todavía')
        
    def get_capital_value(self):
        self.ensure_one()
        total_cap = 0
        # sumo  las acciones y sus primas de emision
        for share in self.env['account.share'].search([('state', 'in', '(suscribed, portfolio, negotiation)')]):
            total_cap += share.price if share.price else 0
        # sumo los aportes irrevocables cobrado
        for cont in self.env['irrevocable.contribution'].search([('state', 'in', '(approved, confirmed)')]):
            total_cap += cont.amount
        # Sumo los Ajustes de Capital por inflación
        for adj in self.env['capital.adjustment'].search([('state', 'in', '(approved, confirmed)')]):
            total_cap += adj.amount

        return total_cap
    def _prepare_reduction_values(self):
        self.ensure_one()
        reduction_values = {
            'name': f'Reducción desde Año Fiscal Cod. - {self.short_name}',
            'date': fields.Date.today(),
            'date_due': fields.Date.today() + relativedelta(days=90),
            'state': 'draft',
            'reduction_type': 'obligatory',
            'notes': 'Creada Desde una Orden de Cancelación, Aprobada por el Gerente de Finanzas',
        }
        return reduction_values
    # LOW LEVELS METHODS
    @api.model
    def create(self, vals):
        if vals.get('short_name', _('New')) == _('New'):
            vals['short_name'] = (self.env['ir.sequence'].next_by_code(
                'account.fiscal.year')) or _('New')
        res = super(AccountFiscalYear, self.create(vals))
        return res

# class FiscalYear(models.Model):
#     _name = "fiscal.year"
#     _inherit = ['fiscal.year']
#     _description = 'Años Válidos'
#     _order = 'short_name desc, name desc'
#     _rec_name = 'short_name'
