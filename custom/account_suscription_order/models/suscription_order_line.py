
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from functools import lru_cache

from markupsafe import Markup
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from odoo.tools.float_utils import float_is_zero, float_compare, float_round
from odoo import models, fields, api, tools, _
from odoo.osv.expression import get_unaccent_wrapper
from odoo.exceptions import ValidationError
from odoo.addons.base.models.res_partner import _tz_get
from odoo.tools.misc import get_lang
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, relativedelta, format_amount, format_date, formatLang, get_lang, groupby
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError

class SuscriptionOrderLine(models.Model):
    _name = 'account.suscription.order.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # _inherits = {'calendar.event': 'event_id'}
    _description = 'Object Share Subscription Line'
    _order = 'ref desc'
    _rec_name = 'ref'

    order_id = fields.Many2one(string='Suscription Order', comodel_name='account.suscription.order', 
                               index=True, 
                               required=False, 
                               readonly=True, 
                               auto_join=True, 
                               ondelete="cascade",
                               check_company=True,
                               help="The order of this line.")
    # compute methods

    @api.depends('product_qty', 'price_unit','currency_id')
    def _compute_totals(self):
        for line in self:
            if line.currency_rate>0.0 :
                line.price_total=line.product_qty*(line.price_unit* line.currency_rate)
            else:
                line.price_total=0

    @api.depends('currency_id', 'company_id', 'date')
    def _compute_currency_rate(self):
        """Funcion para obtener el tipo de cambio"""
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
                date=line.order_id.suscription_date or line.date or fields.Date.context_today(line),
            )
    name=fields.Text(string='Name')
    active=fields.Boolean(string='Active',default=True)
    line_type=fields.Selection(string='Line Type', selection=[
        ('cash','Cash'),
        ('credit','Credit'),
        ('Product','Product')
    ],required=False)

    company_id = fields.Many2one(
        related='order_id.company_id', store=True, readonly=True, precompute=True,
        index=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        tracking=True, help='Currency of the line amount',
        required=False,
        store=True, readonly=False,
    )
    company_currency_id = fields.Many2one(
        string='Company Currency',
        related='order_id.company_currency_id', readonly=True, store=True, precompute=True,
    )

    date = fields.Date(string='Date',
        related='order_id.date_order', store=True,
        copy=False,)
    date_maturity = fields.Date(string='Date Due', related='order_id.date_due',
        store=True,
        copy=False,)
    
    date_planned = fields.Datetime(
        string='Expected Arrival', index=True,
        compute="_compute_price_unit_and_date_planned_and_name", readonly=False, store=True,
        help="Delivery date expected from vendor. This date respectively defaults to vendor pricelist lead time then today's date.")
    
    ref = fields.Char(string='Ref',
        related='order_id.short_name', store=True,
        copy=False,
        index='trigram', readonly=True,
    )
    display_type = fields.Selection(string='Display Type', selection=[
        ('line_section', "Section"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")

    # ==============================================================================================
    #                                          FOR account_move_line
    # ==============================================================================================

    # Money fields
    description = fields.Char(
        string='Description',
    )

    money_type=fields.Selection(string='Type', selection=[
        ('none','None'),
        ('money','Cash'),
        ('check','Check'),
        ('foreign_currency','Foreign Currency'),
        ('wire_transfer','Wire Transfer')
    ],default='none')

    state=fields.Selection(string='State', default='draft', selection=[
        ('draft','Draft'),
        ('suscribed','Suscribed'),
        ('partial_integrated','Partial Integrated'),
        ('integrated','Integrated'),
        ('canceled','Canceled')
    ])
    # Credit fields
    doc_source=fields.Char(string='Document')
    credit_type=fields.Selection(string='Type',selection=[
        ('will_pay','Pagaré'),
        ('invoice','Invoice'),
        ('other','Other'),
    ],required=False)
    partner_id = fields.Many2one(
        string='Partner', comodel_name='res.partner', store=True)
    
    # product or asset fields
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        ondelete='restrict',
    )
    product_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='Unit of Measure',
        store=True, readonly=False, precompute=True,
        domain="[('category_id', '=', product_uom_category_id)]",
        ondelete="restrict",
    )
    product_uom_category_id = fields.Many2one(string='Unit of Measure Cat.',
        comodel_name='uom.category',
        related='product_id.uom_id.category_id',
    )
    product_qty = fields.Float(
        string='Quantity',
        store=True, readonly=False,
        digits='Product Unit of Measure',
        help="The optional quantity expressed by this line, eg: number of product sold. "
             "The quantity is not a legal requirement but is very useful for some reports.", default=1.0
    )
    qty_received_method = fields.Selection([('manual', 'Manual')], string="Received Qty Method", compute='_compute_qty_received_method', store=True,
        help="According to product configuration, the received quantity can be automatically computed by mechanism :\n"
             "  - Manual: the quantity is set manually on the line\n"
             "  - Stock Moves: the quantity comes from confirmed pickings\n")
    qty_received = fields.Float("Received Qty", compute='_compute_qty_received', inverse='_inverse_qty_received', compute_sudo=True, store=True, digits='Product Unit of Measure')
    qty_received_manual = fields.Float("Manual Received Qty", digits='Product Unit of Measure', copy=False)
    product_packaging_id = fields.Many2one('product.packaging', string='Packaging', domain="[('purchase', '=', True), ('product_id', '=', product_id)]", check_company=True,
                                           compute="_compute_product_packaging_id", store=True, readonly=False)
    product_packaging_qty = fields.Float('Packaging Quantity', compute="_compute_product_packaging_qty", store=True, readonly=False)
    # Confirm if it' fixed asset
    asset_profile_id = fields.Many2one(
        comodel_name="account.asset.profile",
        string="Asset Profile",
        compute="_compute_asset_profile",
        store=True,
        readonly=False,
    )
    # === Price fields === #
    price_unit = fields.Float(
        string='Unit Price',
        store=True, readonly=False, help='Amount in currency',
        digits='Product Price', default=0.0
    )
    
    price_total = fields.Monetary(
        string='Total',
        compute='_compute_totals', help='Total Line in Company Currency',
        store=True, 
        readonly=True,
        currency_field='currency_id', default=0.0
    )

    currency_rate = fields.Float(
        compute='_compute_currency_rate', default=0.0,
        help="Currency rate from company currency to document currency.",
    )
    
    amount_residual=fields.Monetary(string='Amount Residual', help='amount pending integration', currency_field='currency_id', )
                                #    _compute_qty_integrated
    
    narration = fields.Html(
        string='Terms and Conditions',
        store=True, readonly=False,
    )
    product_type = fields.Selection(related='product_id.detailed_type', readonly=True)

    account_move_lines=fields.One2many('account.move.line', 'suscription_line_id', string="Suscription Lines", readonly=True, copy=False)
    
    @api.model
    def _get_date_planned(self, seller, po=False):
        """Return the datetime value to use as Schedule Date (``date_planned``) for
           PO Lines that correspond to the given product.seller_ids,
           when ordered at `date_order_str`.

           :param Model seller: used to fetch the delivery delay (if no seller
                                is provided, the delay is 0)
           :param Model po: purchase.order, necessary only if the PO line is
                            not yet attached to a PO.
           :rtype: datetime
           :return: desired Schedule Date for the PO line
        """
        date_order = po.date_order if po else self.order_id.date_order
        if date_order:
            return date_order + relativedelta(days=seller.delay if seller else 0)
        else:
            return datetime.today() + relativedelta(days=seller.delay if seller else 0)
        
    @api.depends('product_qty', 'product_uom_id')
    def _compute_price_unit_and_date_planned_and_name(self):
        for line in self:
            if not line.product_id:
                continue
            params = {'order_id': line.order_id}
            seller = line.product_id._select_seller(
                partner_id=line.partner_id,
                quantity=line.product_qty,
                date=line.order_id.date_order and line.order_id.date_order.date(),
                uom_id=line.product_uom_id,
                params=params)

            if seller or not line.date_planned:
                line.date_planned = line._get_date_planned(seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

            # If not seller, use the standard price. It needs a proper currency conversion.
            if not seller:
                unavailable_seller = line.product_id.seller_ids.filtered(
                    lambda s: s.partner_id == line.order_id.partner_id)
                if not unavailable_seller and line.price_unit and line.product_uom_id == line._origin.product_uom_id:
                    # Avoid to modify the price unit if there is no price list for this partner and
                    # the line has already one to avoid to override unit price set manually.
                    continue
                po_line_uom = line.product_uom_id or line.product_id.uom_po_id
                price_unit = line.env['account.tax']._fix_tax_included_price_company(
                    line.product_id.uom_id._compute_price(line.product_id.standard_price, po_line_uom),
                    line.product_id.supplier_taxes_id,
                    line.taxes_id,
                    line.company_id,
                )
                price_unit = line.product_id.currency_id._convert(
                    price_unit,
                    line.currency_id,
                    line.company_id,
                    line.date_order,
                    False
                )
                line.price_unit = float_round(price_unit, precision_digits=max(line.currency_id.decimal_places, self.env['decimal.precision'].precision_get('Product Price')))
                continue

            price_unit = line.env['account.tax']._fix_tax_included_price_company(seller.price, line.product_id.supplier_taxes_id, line.taxes_id, line.company_id) if seller else 0.0
            price_unit = seller.currency_id._convert(price_unit, line.currency_id, line.company_id, line.date_order, False)
            price_unit = float_round(price_unit, precision_digits=max(line.currency_id.decimal_places, self.env['decimal.precision'].precision_get('Product Price')))
            line.price_unit = seller.product_uom_id._compute_price(price_unit, line.product_uom_id)

            # record product names to avoid resetting custom descriptions
            default_names = []
            vendors = line.product_id._prepare_sellers({})
            for vendor in vendors:
                product_ctx = {'seller_id': vendor.id, 'lang': get_lang(line.env, line.partner_id.lang).code}
                default_names.append(line._get_product_purchase_description(line.product_id.with_context(product_ctx)))
            if not line.name or line.name in default_names:
                product_ctx = {'seller_id': seller.id, 'lang': get_lang(line.env, line.partner_id.lang).code}
                line.name = line._get_product_purchase_description(line.product_id.with_context(product_ctx))

    def _get_product_purchase_description(self, product_lang):
        self.ensure_one()
        name = product_lang.display_name
        if product_lang.description_purchase:
            name += '\n' + product_lang.description_purchase

        return name
    @api.depends('product_id')
    def _compute_qty_received_method(self):
        for line in self:
            if line.product_id and line.product_id.type in ['consu', 'service']:
                line.qty_received_method = 'manual'
            else:
                line.qty_received_method = False

    @api.depends('qty_received_method', 'qty_received_manual')
    def _compute_qty_received(self):
        for line in self:
            if line.qty_received_method == 'manual':
                line.qty_received = line.qty_received_manual or 0.0
            else:
                line.qty_received = 0.0

    @api.onchange('qty_received')
    def _inverse_qty_received(self):
        """ When writing on qty_received, if the value should be modify manually (`qty_received_method` = 'manual' only),
            then we put the value in `qty_received_manual`. Otherwise, `qty_received_manual` should be False since the
            received qty is automatically compute by other mecanisms.
        """
        for line in self:
            if line.qty_received_method == 'manual':
                line.qty_received_manual = line.qty_received
            else:
                line.qty_received_manual = 0.0
    @api.depends('product_id', 'product_qty', 'product_uom_id')
    def _compute_product_packaging_id(self):
        for line in self:
            # remove packaging if not match the product
            if line.product_packaging_id.product_id != line.product_id:
                line.product_packaging_id = False
            # suggest biggest suitable packaging
            if line.product_id and line.product_qty and line.product_uom_id:
                line.product_packaging_id = line.product_id.packaging_ids.filtered('purchase')._find_suitable_product_packaging(line.product_qty, line.product_uom_id) or line.product_packaging_id
    @api.onchange('product_packaging_id')
    def _onchange_product_packaging_id(self):
        if self.product_packaging_id and self.product_qty:
            newqty = self.product_packaging_id._check_qty(self.product_qty, self.product_uom_id, "UP")
            if float_compare(newqty, self.product_qty, precision_rounding=self.product_uom_id.rounding) != 0:
                return {
                    'warning': {
                        'title': _('Warning'),
                        'message': _(
                            "This product is packaged by %(pack_size).2f %(pack_name)s. You should purchase %(quantity).2f %(unit)s.",
                            pack_size=self.product_packaging_id.qty,
                            pack_name=self.product_id.uom_id.name,
                            quantity=newqty,
                            unit=self.product_uom_id.name
                        ),
                    },
                }
    @api.onchange('product_id')
    def onchange_product_id(self):
        if not self.product_id:
            return

        # Reset date, price and quantity since _onchange_quantity will provide default values
        self.price_unit = self.product_qty = 0.0

        self._product_id_change()

        self._suggest_quantity()

    def _product_id_change(self):
        if not self.product_id:
            return

        # TODO: Remove when onchanges are replaced with computes
        if not (self.env.context.get('origin_po_id') and self.product_uom_id and self.product_id.uom_id.category_id == self.product_uom_category_id):
            self.product_uom_id = self.product_id.uom_po_id or self.product_id.uom_id
        product_lang = self.product_id.with_context(
            lang=get_lang(self.env, self.partner_id.lang).code,
            partner_id=self.partner_id.id,
            company_id=self.company_id.id,
        )
        self.name = self._get_product_purchase_description(product_lang)

        self._compute_tax_id()
        
    def _get_product_purchase_description(self, product_lang):
        self.ensure_one()
        name = product_lang.display_name
        if product_lang.description_purchase:
            name += '\n' + product_lang.description_purchase

        return name
    @api.onchange('product_id')
    def onchange_product_id_warning(self):
        if not self.product_id or not self.env.user.has_group('purchase.group_warning_purchase'):
            return
        warning = {}
        title = False
        message = False

        product_info = self.product_id

        if product_info.purchase_line_warn != 'no-message':
            title = _("Warning for %s", product_info.name)
            message = product_info.purchase_line_warn_msg
            warning['title'] = title
            warning['message'] = message
            if product_info.purchase_line_warn == 'block':
                self.product_id = False
            return {'warning': warning}
        return {}
    @api.model
    def _prepare_add_missing_fields(self, values):
        """ Deduce missing required fields from the onchange """
        res = {}
        onchange_fields = ['name', 'price_unit', 'product_qty', 'product_uom_id','date_planned']
        if values.get('order_id') and values.get('product_id') and any(f not in values for f in onchange_fields):
            line = self.new(values)
            line.onchange_product_id()
            for field in onchange_fields:
                if field not in values:
                    res[field] = line._fields[field].convert_to_write(line[field], line)
        return res
    
    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get('display_type', self.default_get(['display_type'])['display_type']):
                values.update(product_id=False, price_unit=0, product_uom_qty=0, product_uom=False, date_planned=False)
            else:
                values.update(self._prepare_add_missing_fields(values))

        lines = super().create(vals_list)
        for line in lines:
            if line.product_id and line.order_id.state == 'purchase':
                msg = _("Extra line with %s ") % (line.product_id.display_name,)
                line.order_id.message_post(body=msg)
        return lines

    def write(self, values):
        if 'display_type' in values and self.filtered(lambda line: line.display_type != values.get('display_type')):
            raise UserError(_("You cannot change the type of a purchase order line. Instead you should delete the current line and create a new line of the proper type."))

        if 'product_qty' in values:
            precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            for line in self:
                if (
                    line.order_id.state == "purchase"
                    and float_compare(line.product_qty, values["product_qty"], precision_digits=precision) != 0
                ):
                    line.order_id.message_post_with_view('purchase.track_po_line_template',
                                                         values={'line': line, 'product_qty': values['product_qty']},
                                                         subtype_id=self.env.ref('mail.mt_note').id)
        if 'qty_received' in values:
            for line in self:
                line._track_qty_received(values['qty_received'])

        return super(SuscriptionOrderLine, self).write(values)
        
    def _update_date_planned_for_lines(self, updated_dates):
        # create or update the activity
        activity = self.env['mail.activity'].search([
        ('summary', '=', _('Date Updated')),
        ('res_model_id', '=', 'purchase.order'),
        ('res_id', '=', self.id),
        ('user_id', '=', self.user_id.id)], limit=1)
        if activity:
            self._update_update_date_activity(updated_dates, activity)
        else:
            self._create_update_date_activity(updated_dates)
        # update the date on PO line
        for line, date in updated_dates:
            line._update_date_planned(date)

    def _create_update_date_activity(self, updated_dates):
        note = Markup('<p>%s</p>\n') % _('%s modified receipt dates for the following products:', self.partner_id.name)
        for line, date in updated_dates:
            note += Markup('<p> - %s</p>\n') % _(
                '%(product)s from %(original_receipt_date)s to %(new_receipt_date)s',
                product=line.product_id.display_name,
                original_receipt_date=line.date_planned.date(),
                new_receipt_date=date.date()
            )
        activity = self.activity_schedule(
            'mail.mail_activity_data_warning',
            summary=_("Date Updated"),
            user_id=self.user_id.id
        )
        # add the note after we post the activity because the note can be soon
        # changed when updating the date of the next PO line. So instead of
        # sending a mail with incomplete note, we send one with no note.
        activity.note = note
        return activity

    def _update_update_date_activity(self, updated_dates, activity):
        for line, date in updated_dates:
            activity.note += Markup('<p> - %s</p>\n') %  _(
                '%(product)s from %(original_receipt_date)s to %(new_receipt_date)s',
                product=line.product_id.display_name,
                original_receipt_date=line.date_planned.date(),
                new_receipt_date=date.date()
            )

    def _write_partner_values(self, vals):
        partner_values = {}
        if 'receipt_reminder_email' in vals:
            partner_values['receipt_reminder_email'] = vals.pop('receipt_reminder_email')
        if 'reminder_date_before_receipt' in vals:
            partner_values['reminder_date_before_receipt'] = vals.pop('reminder_date_before_receipt')
        return vals, partner_values
    

class SuscriptionOrder(models.Model):
    _name = 'account.suscription.order'
    _inherit = 'account.suscription.order'
    
    @api.depends('product_lines','cash_lines','credit_lines')
    def _compute_totals(self):
        for order in self:
            cash_total=0
            credit_total=0
            product_total=0

            lines=order.env['account.suscription.order.line'].read_group(domain=[('order_id','=',order.id)],
                            fields=['price_total'],
                            groupby=['line_type'],orderby='date')
            for line in lines:
                print(line)

            order.cash_total=cash_total
            order.credit_total=credit_total
            order.product_total=product_total
            order.amount_total=cash_total+credit_total+product_total

    @api.onchange('amount_total')
    def _onchange_amount_total(self):
        for record in self:
            if record.amount_total<record.price_total:
                return {
                    'warning': {'title': "Warning", 'message': "The total amount of the lines to be subscribed is less than the value of shares to be acquired. Any difference will be compensated in cash", 'type': 'notification'},
    }

    @api.constrains('price_total','product_total','credit_total','cash_total')
    def _check_total_amount(self):
        for rec in self:
            if rec.price_total<(rec.product_total+rec.credit_total+rec.cash_total):
                raise ValidationError(_('The total amount of the lines to be subscribed must coincide with the total of the shares acquired'))
            
    @api.onchange('date_planned')
    def onchange_date_planned(self):
        if self.date_planned:
            self.order_line_ids.filtered(lambda line: not line.display_type).date_planned = self.date_planned

    order_line_ids = fields.One2many(string='Products Lines', comodel_name='account.suscription.order.line', 
                                    inverse_name='order_id',
                                    copy=False, 
                                    readonly=False,
                                    help='Order Lines Availables')
    
    amount_total=fields.Monetary(string='Total', currency_field='company_currency_id',)
    # Total Fields
    cash_total=fields.Monetary(string='Cash Total', store=True, readonly=True,
                                currency_field='company_currency_id', help='Resulting Total of the Cash lines to be subscribed, in company currency')
    credit_total=fields.Monetary(string='Credit Total', store=True, readonly=True,
                                currency_field='company_currency_id', help='Resulting Total of the Credit lines to be subscribed, in company currency')
    product_total=fields.Monetary(string='Product Total', store=True, readonly=True,
                                currency_field='company_currency_id', help='Resulting Total of the Product lines to be subscribed, in company currency')
    
    @api.depends('order_line_ids.date_planned')
    def _compute_date_planned(self):
        """ date_planned = the earliest date_planned across all order lines. """
        for order in self:
            dates_list = order.order_line_ids.filtered(lambda x: not x.display_type and x.date_planned).mapped('date_planned')
            if dates_list:
                order.date_planned = min(dates_list)
            else:
                order.date_planned = False