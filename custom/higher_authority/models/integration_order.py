# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import collections
from functools import lru_cache
import hashlib
import re
import pytz
import requests
from odoo.exceptions import UserError
from werkzeug import urls

from datetime import datetime, timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api, tools

from odoo.osv.expression import get_unaccent_wrapper

from odoo.exceptions import ValidationError
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import math
import babel.dates
import logging

from odoo.addons.base.models.res_partner import _tz_get
from odoo.addons.calendar.models.calendar_attendee import Attendee
from odoo.addons.calendar.models.calendar_recurrence import weekday_to_field, RRULE_TYPE_SELECTION, END_TYPE_SELECTION, MONTH_BY_SELECTION, WEEKDAY_SELECTION, BYDAY_SELECTION
from odoo.tools.translate import _
from odoo.tools.misc import get_lang
from odoo.tools import pycompat
from odoo.exceptions import UserError, AccessError


class IntegrationOrder(models.Model):
    _name = 'integration.order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Objeto Hoja de Integración'
    _order = 'short_name desc'
    _rec_name = 'short_name'

    # metodos computados
    @api.depends('product_id', 'cash_id')
    def _compute_qty_to_subscribe(self):
        for order in self:
            for line in order.integration_lines:
                order.qty_to_subscribe+=line.amount_currency \
                      if line.amount_currency and line.amount_currency>0 else line.price_total
    

    @api.depends('shares')
    def _compute_amount_total(self):
        for order in self:
            for share in order.shares:
                amount_total += share.price

    @api.depends('integration_order')
    def _compute_qty_integrated(self):
        for order in self:
            for integration in order.integration_lines:
                order.qty_integrated+=integration.qty_to_integrate
                if order.qty_integrated==integration.qty_to_integrate:
                    order.pending=False
                else:
                    order.pending=True
    @api.depends('qty_integrated')
    def _compute_qty_pending(self):
        for order in self:
            order.qty_pending=order.qty_integrated-order.amount_total
    


    short_name=fields.Char(string='Referencia', required=True)
    # colocar una secuencia
    code = fields.Integer(string='Código', required=True)
    int_date_expected=fields.Date(string='Fecha de Integración Esperada', help='Fecha de integración prometida por el accionista', readonly=True)

    int_date=fields.Date(string='Fecha de Integración', readonly=True)
    pending=fields.Boolean(string='Pendiente', default=True)
    nominal_value = fields.Float(related='share_issuance.nominal_value',
        string='Valor de Emisión', required=True, copy=True)
    price = fields.Float(related='share_issuance.price',string='Valor pactado en la suscripción',
                         help='El el valor al cual se vendió la accion, el monto total que pago el accionista por adquirir la acción', readonly=True, copy=True, readonly=True, store=True)

    issue_premium = fields.Float(related='share_issuance.issue_premium',
        string='Prima de emision', help='Cotizacion sobre la par', readonly=True, store=True)

    issue_discount = fields.Float(related='share_issuance.issue_discount',
        string='Descuento de Emisión', help='Descuento bajo la par', readonly=True, store=True)

    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company.id)
    currency_id = fields.Many2one('res.currency', 'Currency', required=True,
                                  default=lambda self: self.env.company.currency_id.id)
    qty_to_integrate=fields.Monetary(string='Cantidad a Integrar', currency_field='company_currency_id', default=lambda self: self.subscription_order.qty_pending)
    # === Currency fields === #
    company_currency_id = fields.Many2one(
        string='Company Currency',
        related='company_id.currency_id', readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        tracking=True,
        required=True,
        compute='_compute_currency_id', inverse='_inverse_currency_id', store=True, readonly=False, precompute=True,
        states={'posted': [('readonly', True)], 'cancel': [('readonly', True)]},
    )
    amount_total = fields.Monetary(
        string='Total', store=True, readonly=True, compute='_compute_amount_total')

    qty_integrated=fields.Monetary(string='Cantidad Integrada', currency_field='company_currency_id', compute='_compute_qty_integrated', help='Cantidad que se ha integrado')

    qty_pending=fields.Monetary(string='Cantidad penndiente de integrar',currency_field='company_currency_id',compute='_compute_qty_pending', help='Cantidad que no se ha subscripto')
    # campos relacionales

    subscription_order=fields.Many2one(string='Orden de Subscripción', comodel_name='subscription.order', help='Orden de suscripción relacionada')
    shares=fields.One2many(string='Acciones a emitir', help='Acciones creadas', comodel_name='account.share', inverse_name='subscription_order', index=True)

    integration_lines=fields.One2many(string='Líneas de Orden', comodel_name='integration.order.line', inverse_name='order_id',copy=False, readonly=True,
        domain=[],
        states={'draft': [('readonly', False)]})
    
    account_move=fields.Many2one(string='Asiento contable', comodel_name='account.move', index=True, help='Asiento contable Relacionado', readonly=True, domain=[('move_type','=','integration')])
        # === Payment fields === #

    class IntegrationOrderLine(models.Model):
        _name = 'integration.order.line'
        _inherit = ['mail.thread', 'mail.activity.mixin']
        # _inherits = {'calendar.event': 'event_id'}
        _description = 'Objeto Línea Integración de Acciones'
        _order = 'short_name desc, move_name desc'
        _rec_name = 'short_name'

    order_id=fields.Many2one(string='Orden', comodel_name='integration.order',        index=True, required=True, readonly=True, auto_join=True, ondelete="cascade",
        check_company=True,
        help="La orden de esta linea.")
    
    @api.depends('quantity', 'discount', 'price_unit', 'tax_ids', 'currency_id')
    def _compute_totals(self):
        for line in self:
            if line.type != 'product':
                line.price_total = line.price_subtotal = False
            # Compute 'price_subtotal'.
            line_discount_price_unit = line.price_unit * (1 - (line.discount / 100.0))
            subtotal = line.quantity * line_discount_price_unit

            # Compute 'price_total'.
            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    line_discount_price_unit,
                    quantity=line.quantity,
                    currency=line.currency_id,
                    product=line.product_id,
                    partner=line.partner_id,
                    is_refund=line.is_refund,
                )
                line.price_subtotal = taxes_res['total_excluded']
                line.price_total = taxes_res['total_included']
            else:
                line.price_total = line.price_subtotal = subtotal

    @api.depends('currency_id', 'company_id', 'move_id.date')
    def _compute_currency_rate(self):
        @lru_cache()
        def get_rate(from_currency, to_currency, company, date):
            return self.env['res.currency']._get_conversion_rate(
                from_currency=from_currency,
                to_currency=to_currency,
                company=company,
                date=date,
            )
        for line in self:
            line.currency_rate = get_rate(
                from_currency=line.company_currency_id,
                to_currency=line.currency_id,
                company=line.company_id,
                date=line.move_id.invoice_date or line.move_id.date or fields.Date.context_today(line),
            )
    @api.depends('currency_rate', 'amount')
    def _compute_amount_currency(self):
        for line in self:
            if line.amount_currency is False:
                line.amount_currency = line.currency_id.round(line.amount * line.currency_rate)
            if line.currency_id == line.company_id.currency_id:
                line.amount_currency = line.amount
    @api.depends('order_id.currency_id')
    def _compute_currency_id(self):
        for line in self:
                line.currency_id = line.currency_id or line.company_id.currency_id
    @api.depends('currency_id', 'company_currency_id')
    def _compute_same_currency(self):
        for record in self:
            record.is_same_currency = record.currency_id == record.company_currency_id
    @api.onchange('amount_currency', 'currency_id')
    def _inverse_amount_currency(self):
        for line in self:
            if line.currency_id == line.company_id.currency_id and line.value != line.amount_currency:
                line.value = line.amount_currency
            elif (
                line.currency_id != line.company_id.currency_id
                and not line.order_id.is_invoice(True)
                and not self.env.is_protected(self._fields['value'], line)
            ):
                line.value = line.company_id.currency_id.round(line.amount_currency / line.currency_rate)
        # Do not depend on `move_id.partner_id`, the inverse is taking care of that
    def _compute_partner_id(self):
        for line in self:
            line.partner_id = line.order_id.partner_id.commercial_partner_id  
    @api.depends('product_id', 'product_uom_id')
    def _compute_tax_ids(self):
        """Completa los impuestos de la linea automaticamente, a partir de los impuestos
            del producto y la configuracion de la empresa
        """
        for line in self:
            # /!\ Don't remove existing taxes if there is no explicit taxes set on the account.
            if line.product_id or line.account_id.tax_ids or not line.tax_ids:
                line.tax_ids = line._get_computed_taxes()
    def _get_computed_taxes(self):
        self.ensure_one()

        if self.product_id.taxes_id:
            tax_ids = self.product_id.taxes_id.filtered(lambda tax: tax.company_id == self.order_id.company_id)
        else:
            tax_ids = self.account_id.tax_ids.filtered(lambda tax: tax.type_tax_use == 'sale')
        if not tax_ids and self.display_type == 'product':
            tax_ids = self.order_id.company_id.account_sale_tax_id
        
        if self.product_id.supplier_taxes_id:
            tax_ids = self.product_id.supplier_taxes_id.filtered(lambda tax: tax.company_id == self.order_id.company_id)
        else:
            tax_ids = self.account_id.tax_ids.filtered(lambda tax: tax.type_tax_use == 'purchase')
        if not tax_ids:
            tax_ids = self.order_id.company_id.account_purchase_tax_id
        else:
            # Miscellaneous operation.
            tax_ids = self.account_id.tax_ids

        if self.company_id and tax_ids:
            tax_ids = tax_ids.filtered(lambda tax: tax.company_id == self.company_id)

        if tax_ids and self.move_id.fiscal_position_id:
            tax_ids = self.move_id.fiscal_position_id.map_tax(tax_ids)

        return tax_ids
    
    type = fields.Selection(string='Tipo', required=True, help='Campo técnico usado para establecer el tipo de asiento', selection=[
        ('cash', 'Efectivo o Banco'),
        ('credit', 'Crédito'),
        ('asset', 'Activo'),
        ('product', 'Producto')
    ])

    short_name = fields.Char(string='Referencia')

    company_id = fields.Many2one(
        related='order_id.company_id', store=True, readonly=True, precompute=True,
        index=True,
    )
    company_currency_id = fields.Many2one(
        string='Company Currency',
        related='order_id.company_currency_id', readonly=True, store=True, precompute=True,
    )
    move_name = fields.Char(
        string='Number',
        related='order_id.name', store=True,
        index='btree',
    )
    parent_state = fields.Selection(related='order_id.state', store=True)
    date = fields.Date(
        related='order_id.date', store=True,
        copy=False,
        group_operator='min',
    )
    ref = fields.Char(
        related='order_id.short_name', store=True,
        copy=False,
        index='trigram',
    )

    sequence = fields.Integer(string='Sequence', store=True, readonly=False, precompute=True)

    # === Accountable fields === #
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Account',
        index=True,
        auto_join=True,
        ondelete="cascade",
        domain="[('deprecated', '=', False), ('company_id', '=', company_id), ('is_off_balance', '=', False)]",
        check_company=True,
        tracking=True,
    )
    name = fields.Char(
        string='Label', store=True, readonly=False, precompute=True,
        tracking=True,
    )
    amount=fields.Monetary(string='Importe', help='Importe del monto aportado', currency_field='company_currency_id')
    currency_rate = fields.Float(
        compute='_compute_currency_rate',
        help="Currency rate from company currency to document currency.",
    )
    amount_currency = fields.Monetary(
        string='Amount in Currency',
        group_operator=None,
        compute='_compute_amount_currency', inverse='_inverse_amount_currency', store=True, readonly=False, precompute=True,
        help="The amount expressed in an optional other currency if it is a multi-currency entry.")
    company_currency_id = fields.Many2one(
        string='Company Currency',
        related='order_id.company_currency_id', readonly=True, store=True, precompute=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        compute='_compute_currency_id', store=True, readonly=False, precompute=True,
        required=True,
    )
    is_same_currency = fields.Boolean(compute='_compute_same_currency')
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner',
        compute='_compute_partner_id', inverse='_inverse_partner_id', store=True, readonly=False, precompute=True,
        ondelete='restrict',
    )

    # === Tax fields === #
    tax_ids = fields.Many2many(
        comodel_name='account.tax',
        string="Taxes",
        compute='_compute_tax_ids', store=True, readonly=False, precompute=True,
        context={'active_test': False},
        check_company=True,
    )
    group_tax_id = fields.Many2one(
        comodel_name='account.tax',
        string="Originator Group of Taxes",
        index='btree_not_null',
    )
    tax_line_id = fields.Many2one(
        comodel_name='account.tax',
        string='Originator Tax',
        related='tax_repartition_line_id.tax_id', store=True, precompute=True,
        ondelete='restrict',
        help="Indicates that this journal item is a tax line")
    tax_group_id = fields.Many2one(  # used in the widget tax-group-custom-field
        string='Originator tax group',
        related='tax_line_id.tax_group_id', store=True, precompute=True,
    )
    tax_base_amount = fields.Monetary(
        string="Base Amount",
        readonly=True,
        currency_field='company_currency_id',
    )
    tax_repartition_line_id = fields.Many2one(
        comodel_name='account.tax.repartition.line',
        string="Originator Tax Distribution Line",
        ondelete='restrict',
        readonly=True,
        check_company=True,
        help="Tax distribution line that caused the creation of this move line, if any")
    tax_tag_ids = fields.Many2many(
        string="Tags",
        comodel_name='account.account.tag',
        ondelete='restrict',
        context={'active_test': False},
        tracking=True,
        help="Tags assigned to this line by the tax creating it, if any. It determines its impact on financial reports.",
    )

    # === Reconciliation fields === #

    # === Related fields ===
    account_type = fields.Selection(
        related='account_id.account_type',
        string="Internal Type",
    )
    account_internal_group = fields.Selection(related='account_id.internal_group')
    account_root_id = fields.Many2one(
        related='account_id.root_id',
        string="Account Root",
        store=True,
    )

    # ==============================================================================================
    #                                          FOR account_move_line
    # ==============================================================================================

    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        inverse='_inverse_product_id',
        ondelete='restrict',
    )
    product_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='Unit of Measure',
        compute='_compute_product_uom_id', store=True, readonly=False, precompute=True,
        domain="[('category_id', '=', product_uom_category_id)]",
        ondelete="restrict",
    )
    product_uom_category_id = fields.Many2one(
        comodel_name='uom.category',
        related='product_id.uom_id.category_id',
    )
    quantity = fields.Float(
        string='Quantity',
        compute='_compute_quantity', store=True, readonly=False, precompute=True,
        digits='Product Unit of Measure',
        help="The optional quantity expressed by this line, eg: number of product sold. "
             "The quantity is not a legal requirement but is very useful for some reports.",
    )
    date_maturity = fields.Date(
        string='Due Date',
        index=True,
        tracking=True,
        help="This field is used for payable and receivable journal entries. "
             "You can put the limit date for the payment of this line.",
    )

    # === Price fields === #
    price_unit = fields.Float(
        string='Unit Price',
        compute="_compute_price_unit", store=True, readonly=False, precompute=True,
        digits='Product Price',
    )
    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_totals', store=True,
        currency_field='currency_id',
    )
    price_total = fields.Monetary(
        string='Total',
        compute='_compute_totals', store=True,
        currency_field='currency_id',
    )
    discount = fields.Float(
        string='Discount (%)',
        digits='Discount',
        default=0.0,
    )

        # campos relacionales
    cash_lines=fields.One2many(string='Líneas de Efectivo', comodel_name='integration.order.line', inverse_name='order_id',copy=False, readonly=True,
        domain=[('type','=','cash')],
        states={'draft': [('readonly', False)]})
    credit_lines=fields.One2many(string='Líneas de Crédito', comodel_name='integration.order.line', inverse_name='order_id',copy=False, readonly=True,
        domain=[('type','=','credit')],
        states={'draft': [('readonly', False)]})
    asset_lines=fields.One2many(string='Líneas de Activos', comodel_name='integration.order.line', inverse_name='order_id',copy=False, readonly=True,
        domain=[('type','=','credit')],
        states={'draft': [('readonly', False)]}, help='Activos fijos o intangibles')
    product_lines=fields.One2many(string='Líneas de Activos', comodel_name='integration.order.line', inverse_name='order_id',copy=False, readonly=True,
        domain=[('type','=','product')],
        states={'draft': [('readonly', False)]}, help='Sólo Productos Físicos no servicios')
    
    account_move=fields.Many2one(string='Asiento', comodel_name='account.move', help='Asiento contable integrado')
    payment_id = fields.Many2one(
        comodel_name='account.payment',
        string="Pago",
        index='btree_not_null',
        copy=False,
        check_company=True,
        help='asiento contable generado para las lineas de efectivo'
    )
    integrated=fields.Boolean(string='Integrado', default=False, readonly=True)

    # campos para arrastrar los activos Fijos

    asset_profile_id = fields.Many2one(
        comodel_name="account.asset.profile",
        string="Asset Profile",
        compute="_compute_asset_profile",
        store=True,
        readonly=False,
    )
    asset_id = fields.Many2one(
        comodel_name="account.asset",
        string="Asset",
        ondelete="restrict",
    )

    @api.depends("account_id", "asset_id")
    def _compute_asset_profile(self):
        for rec in self:
            if rec.account_id.asset_profile_id and not rec.asset_id:
                rec.asset_profile_id = rec.account_id.asset_profile_id
            elif rec.asset_id:
                rec.asset_profile_id = rec.asset_id.profile_id

    @api.onchange("asset_profile_id")
    def _onchange_asset_profile_id(self):
        if self.asset_profile_id.account_asset_id:
            self.account_id = self.asset_profile_id.account_asset_id
    # -------------------------------------------------------------------------
    # INVERSE METHODS
    # -------------------------------------------------------------------------

    @api.onchange('partner_id')
    def _inverse_partner_id(self):
        self._conditional_add_to_compute('account_id', lambda line: (
            line.display_type == 'payment_term'  # recompute based on settings
            or (line.move_id.is_invoice(True) and line.display_type == 'product' and not line.product_id)  # recompute based on most used account
        ))