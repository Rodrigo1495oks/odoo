# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from bisect import bisect_left
from collections import defaultdict
import re

class Test(models.Model):
    _name = "custom.test"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Model for test"
    _order = "short_name desc"
    _check_company_auto = True
    _rec_name='short_name'

    name=fields.Char(string='Name', index=True, size=32)
    short_name = fields.Char(string='Referencia', 
                             default='New',
                             required=True, 
                             copy=False, 
                             readonly=True)
    
    date=fields.Datetime(string='Date', index=True, copy=False, readonly=True, default=fields.Datetime.now, help='Record Date')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company.id)
    active = fields.Boolean(string='Activo: ', default=True)
    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('progress','En Curso'),
        ('count','Conteo de Votos'),
        ('finished', 'Finalizada'),
        ('canceled', 'Cancelada')
    ], default='draft')

    partner_text=fields.Text(string='Texto de Prueba')

    total=fields.Float(string='Total',
                         readonly=True, 
                         help='Porcentaje de Asistencia a la Reunión', store=True,)
    
    user_id=fields.Many2one(string='Usuario', comodel_name='res.users', default=lambda self: self.env.user, readonly=True)
    track = fields.Char(string='Seguimiento', size=10, track_visibility=True, index='btree', store=True)
    no_track = fields.Char(string='sin Seguimiento', size=10, track_visibility=True, index='btree', store=True)

    def name_get(self):
        result = []
        for ast in self:
            name = '%s - (%s)' % (ast.name, ast.short_name)
            result.append((ast.id, name))
        return result

    # campos computados
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            args = args or []
            domain = [('state','=','new'),('active','=',True)]
            return self.search(expression.AND([domain, args]), limit=limit).name_get()
        return super(Test, self).name_search(name=name, args=args, operator=operator, limit=limit)

    
    account_ids=fields.Many2many(string='Cuentas', comodel_name='account.account', column1='test',column2='account_account',relation='test_account_account_rel')

    # Helpers

    def button_test(self):
        accounts=self.env['account.account'].read_group(
            domain=[],
            fields=['id','name','code','company_id'],
            groupby=['account_type']
        )
        for group in accounts:
            print(group)
            # print(group.get('company_id')[0])
            print((group.get('id')))
            print((group.get('name')))
            print((group.get('code')))
            print((group.get('internal_group')))

        accounts=self.env['account.account'].search_read(
            domain=[('account_type','in',['asset_receivable','asset_cash'])],
            fields=['name','currency_id','code','deprecated','account_type'],
            order=''
        )
        for group in accounts:
            print(group)

        print(self.env['account.account'].ids)
        print(self.ids, '-------ids de test')

        lista_de_cuentas=[k.get('id') for k in self.env['account.account'].search([('used','=', True)]).read(['id'])]

        print(lista_de_cuentas, '----lista de cuentas')
        balances = {
            read['account_id'][0]: read['balance']
            for read in self.env['account.move.line'].search_read(
                domain=[('account_id', 'in', lista_de_cuentas), ('parent_state', '=', 'posted')],
                fields=['balance', 'account_id'],
                order='date'
            )
        }

        print(balances, '----------balances')
        for account in balances:
            print('account:--------', account)
        for record in self.env['account.account'].browse(lista_de_cuentas):
            print(balances.get(record.id, 0))
        # ''.capitalize()
        print('selection load -------------------')
        states = []
        raw_data = self.env['account.suscription.order.stage'].search([]).read(['order_state'])
        for kv in raw_data:
            states.append((kv['order_state'],kv['order_state'].capitalize()))
        print(states)
        print(self.search([], limit=1))

        for rec in self.search([], limit=1):
            print(rec)
        return

        partner=self.env['res.partner'].search([])
        votes=self.env['assembly.meeting.vote'].search([])
        print(partner)
        print(votes)
        print(partner+votes)
        for rec in (partner+votes):
            print(',,,,,,_: %s'%(rec))

        # low level methods

    @api.model
    def create(self, vals):
        if not vals.get('date', fields.Datetime.now):
            vals['date']=fields.Datetime.now
        if vals.get('short_name', _('New')) == _('New'):
            seq_date = None
            if 'date' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date']))
                vals['short_name'] = self.env['ir.sequence'].next_by_code(
                    'custom.test', sequence_date=seq_date) or _('New')

        self.env['custom.test.line'].create({
            'name':'New Line',
            "short_name":'Código %s - %s' % (vals.get('date') ,vals.get('short_name')),
            'order_id': self.id,
            'amount': 5000
        })
        return super().create(vals)

