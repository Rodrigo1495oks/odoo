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


class SoProductLine(models.Model):
    _name = 'account.suscription.product.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # _inherits = {'calendar.event': 'event_id'}
    _description = 'Object Share Subscription Product Line'
    _order = 'short_name,date desc'
    _rec_name = 'short_name'

    short_name = fields.Char(string='Reference', default='New', required=True, copy=False, readonly=True,
                             store=True,
                             index=True)
    sequence = fields.Integer(string='n', default=1)
    order_id = fields.Many2one(string='Suscription Order', comodel_name='account.suscription.order',
                               index=True,
                               required=False,
                               readonly=True,
                               auto_join=True,
                               ondelete="cascade",
                               check_company=True,
                               help="The order of this line.")

    name = fields.Text(string='Name')
    active = fields.Boolean(string='Active', default=True)

    company_id = fields.Many2one(
        related='order_id.company_id', store=True, readonly=True,
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
        related='order_id.company_currency_id', readonly=True, store=True,
    )

    date = fields.Date(string='Date',
                       related='order_id.date_order', store=True,
                       copy=False, )
    date_maturity = fields.Date(string='Date Due', related='order_id.date_due',
                                store=True,
                                copy=False, )
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
    state = fields.Selection(string='State', default='draft', selection=[
        ('draft', 'Draft'),
        ('subscribed', 'Subscribed'),
        ('partial_contributed', 'Partial Contributed'),
        ('contributed', 'Totally Contributed'),
        ('integrated', 'Integrated'),
        ('canceled', 'Canceled')
    ], compute='_compute_state')

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
    amount_integrated = fields.Monetary(string='Credit Integrated', currency_field='company_currency_id', store=True,
                                        compute='_compute_amount_integrated')
    amount_to_integrate = fields.Monetary(string='Credit to Integrate', currency_field='company_currency_id',
                                          store=True, compute='_compute_amount_integrated')
    currency_rate = fields.Float(
        compute='_compute_currency_rate', default=0.0,
        help="Currency rate from company currency to document currency.",
    )

    narration = fields.Html(
        string='Terms and Conditions',
        store=True, readonly=False,
    )

    move_lines_ids = fields.One2many(comodel_name='account.move.line', inverse_name='integration_product_line_id',
                                     string="Integration Lines",
                                     readonly=True, copy=False,
                                     domain=[('move_id.move_type', '=', 'integration')])
    suscription_line_ids = fields.One2many(comodel_name='account.move.line', inverse_name='suscription_product_line_id',
                                           string="Suscription Lines",
                                           readonly=True, copy=False,
                                           domain=[('move_id.move_type', '=', 'suscription')])
    partner_id=fields.Many2one(string='Partner', comodel_name='res.partner', default=lambda l: l.order_id.partner_id)

    # product or asset fields

    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        ondelete='restrict',
    )
    product_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='Unit of Measure',
        store=True, readonly=False,
        domain="[('category_id', '=', product_uom_category_id)]",
        ondelete="restrict",
    )
    product_uom_qty = fields.Float(string='Total Quantity', compute='_compute_product_uom_qty', store=True)
    product_uom_category_id = fields.Many2one(string='Unit of Measure Cat.',
                                              comodel_name='uom.category',
                                              related='product_id.uom_id.category_id',
                                              )
    product_qty = fields.Float(compute='_compute_product_qty',
                               string='Quantity',
                               store=True, readonly=False, default=1.0,
                               digits='Product Unit of Measure',
                               help="The optional quantity expressed by this line, eg: number of product sold. "
                                    "The quantity is not a legal requirement but is very useful for some reports.",
                               )

    qty_received_method = fields.Selection([('manual', 'Manual')], string="Received Qty Method",
                                           compute='_compute_qty_received_method', store=True,
                                           help="According to product configuration, the received quantity can be automatically computed by mechanism :\n"
                                                "  - Manual: the quantity is set manually on the line\n"
                                                "  - Stock Moves: the quantity comte_amount_integrated'",
                                           readonly=True,
                                           digits='Pres from confirmed pickings\n"')
    qty_received = fields.Float("Received Qty", compute='_compute_qty_received', inverse='_inverse_qty_received',
                                compute_sudo=True, store=True, digits='Product Unit of Measure')
    qty_received_manual = fields.Float("Manual Received Qty", digits='Product Unit of Measure', copy=False)
    product_type = fields.Selection(related='product_id.detailed_type', readonly=True)
    product_packaging_id = fields.Many2one('product.packaging', string='Packaging',
                                           domain="[('purchase', '=', True), ('product_id', '=', product_id)]",
                                           check_company=True,
                                           compute="_compute_product_packaging_id", store=True, readonly=False)
    product_packaging_qty = fields.Float('Packaging Quantity', compute="_compute_product_packaging_qty", store=True,
                                         readonly=False)
    # Confirm if it' fixed asset
    asset_profile_id = fields.Many2one(
        comodel_name="account.asset.profile",
        string="Asset Profile",
        store=True,
        readonly=False,
    )
    taxes_id = fields.Many2many('account.tax', string='Taxes',
                                domain=['|', ('active', '=', False), ('active', '=', True)])

    @api.depends('amount_integrated', 'amount_to_integrate', 'display_type', 'amount_integrated',
                 'amount_to_integrate')
    def _compute_state(self):
        for line in self:
            if line.display_type:
                line.state = 'draft'
                continue
            line.state = 'subscribed' if all(
                [len(line.suscription_line_ids) > 0, line.amount_integrated < 1]) else 'draft'
            line.state = 'partial_contributed' if all(
                [len(line.suscription_line_ids) > 0, line.amount_integrated > 0,
                 line.amount_to_integrate > 0]) else 'draft'
            line.state = 'contributed' if all([len(line.suscription_line_ids) > 0, line.amount_integrated > 0,
                                               line.amount_to_integrate == 0]) else 'draft'

    @api.depends('product_qty', 'price_unit', 'currency_id')
    def _compute_totals(self):
        for line in self:
            if line.currency_rate > 0.0:
                line.price_total = line.product_qty * (line.price_unit * line.currency_rate)
            else:
                line.price_total = 0

    @api.depends('move_lines_ids.move_id.state', 'move_lines_ids.quantity', 'order_id.state', 'price_total', )
    def _compute_amount_integrated(self):
        """ determines the integrated amount of the cash and credit lines"""
        for line in self:
            if not line.display_type:
                # compute qty_invoiced
                amount = 0.0
                for inv_line in line._get_integrated_lines():
                    if inv_line.move_id.state not in ['cancel'] or inv_line.move_id.payment_state == 'invoicing_legacy':
                        if inv_line.move_id.move_type == 'integration':
                            amount += inv_line.debit
                line.amount_integrated = amount
                line.amount_to_integrate = line.price_total - line.amount_integrated
            else:
                line.amount_integrated = 0

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
            if not line.display_type:
                line.currency_rate = get_rate(
                    from_currency=line.company_currency_id,
                    to_currency=line.currency_id,
                    company=line.company_id,
                    date=line.order_id.date_order or line.date or fields.Date.context_today(line),
                )
            else:
                line.currency_rate = 0

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

    def _get_integrated_lines(self):
        self.ensure_one()
        if self._context.get('accrual_entry_date'):
            return self.move_lines_ids.filtered(
                lambda l: l.move_id.date and l.move_id.date <= self._context['accrual_entry_date']
            )
        else:
            return self.move_lines_ids

    @api.model
    def _prepare_suscription_order_line(self, product_id, product_qty, product_uom_id, company_id, supplier, po):
        partner = supplier.partner_id
        uom_po_qty = product_uom_id._compute_quantity(product_qty, product_id.uom_po_id)
        # _select_seller is used if the supplier have different price depending
        # the quantities ordered.
        seller = product_id.with_company(company_id)._select_seller(
            partner_id=partner,
            quantity=uom_po_qty,
            date=po.date_order and po.date_order.date(),
            uom_id=product_id.uom_po_id)

        product_taxes = product_id.supplier_taxes_id.filtered(lambda x: x.company_id.id == company_id.id)
        taxes = po.fiscal_position_id.map_tax(product_taxes)

        price_unit = self.env['account.tax']._fix_tax_included_price_company(
            seller.price, product_taxes, taxes, company_id) if seller else 0.0
        if price_unit and seller and po.currency_id and seller.currency_id != po.currency_id:
            price_unit = seller.currency_id._convert(
                price_unit, po.currency_id, po.company_id, po.date_order or fields.Date.today())

        product_lang = product_id.with_prefetch().with_context(
            lang=partner.lang,
            partner_id=partner.id,
        )
        name = product_lang.with_context(seller_id=seller.id).display_name
        if product_lang.description_purchase:
            name += '\n' + product_lang.description_purchase

        date_planned = self.order_id.date_planned or self._get_date_planned(seller, po=po)

        return {
            'name': name,
            'product_qty': uom_po_qty,
            'product_id': product_id.id,
            'product_uom': product_id.uom_po_id.id,
            'price_unit': price_unit,
            'date_planned': date_planned,
            'taxes_id': [(6, 0, taxes.ids)],
            'order_id': po.id,
        }

    @api.model
    def _prepare_add_missing_fields(self, values):
        """ Deduce missing required fields from the onchange """
        res = {}
        onchange_fields = ['name', 'price_unit', 'product_qty', 'product_uom_id', 'date_planned']
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
            if line.product_id and line.order_id.state == 'approved':
                msg = _("Extra line with %s ") % (line.product_id.display_name,)
                line.order_id.message_post(body=msg)
        return lines

    def write(self, values):
        if 'display_type' in values and self.filtered(lambda line: line.display_type != values.get('display_type')):
            raise UserError(
                _("You cannot change the type of a purchase order line. Instead you should delete the current line and create a new line of the proper type."))

        if 'product_qty' in values:
            precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            for line in self:
                if (
                        line.order_id.state == "subscribed"
                        and float_compare(line.product_qty, values["product_qty"], precision_digits=precision) != 0
                ):
                    line.order_id.message_post_with_view('purchase.track_po_line_template',
                                                         values={'line': line, 'product_qty': values['product_qty']},
                                                         subtype_id=self.env.ref('mail.mt_note').id)
        if 'qty_received' in values:
            for line in self:
                line._track_qty_received(values['qty_received'])

        return super(SoProductLine, self).write(values)

    def _update_date_planned_for_lines(self, updated_dates):
        # create or update the activity
        activity = self.env['mail.activity'].search([
            ('summary', '=', _('Date Updated')),
            ('res_model_id', '=', 'account.suscription.order'),
            ('res_id', '=', self.id),
            ('user_id', '=', self.order_id.user_id.id)], limit=1)
        if activity:
            self._update_update_date_activity(updated_dates, activity)
        else:
            self._create_update_date_activity(updated_dates)
        # update the date on PO line
        for line, date in updated_dates:
            line._update_date_planned(date)

    def _create_update_date_activity(self, updated_dates):
        note = Markup('<p>%s</p>\n') % _('%s modified receipt dates for the following products:',
                                         self.order_id.partner_id.name)
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
            user_id=self.order_id.user_id.id
        )
        # add the note after we post the activity because the note can be soon
        # changed when updating the date of the next PO line. So instead of
        # sending a mail with incomplete note, we send one with no note.
        activity.note = note
        return activity

    def _update_update_date_activity(self, updated_dates, activity):
        for line, date in updated_dates:
            activity.note += Markup('<p> - %s</p>\n') % _(
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

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get('display_type', self.default_get(['display_type'])['display_type']):
                values.update(product_id=False, price_unit=0, product_uom_qty=0, product_uom_id=False,
                              date_planned=False)
            else:
                values.update(self._prepare_add_missing_fields(values))

        lines = super().create(vals_list)
        for line in lines:
            if line.product_id and line.order_id.state == 'subscribed':
                msg = _("Extra line with %s ") % (line.product_id.display_name,)
                line.order_id.message_post(body=msg)
        return lines

    @api.ondelete(at_uninstall=False)
    def _unlink_except_purchase_or_done(self):
        for line in self:
            if line.order_id.state in ['subscribed', 'new', 'finished']:
                state_description = {state_desc[0]: state_desc[1] for state_desc in
                                     self._fields['state']._description_selection(self.env)}
                raise UserError(_('Cannot delete a suscription order line which is in state \'%s\'.') % (
                    state_description.get(line.state),))

    @api.model
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, supplier, po):
        partner = supplier.partner_id
        uom_po_qty = product_uom._compute_quantity(product_qty, product_id.uom_po_id)
        # _select_seller is used if the supplier have different price depending
        # the quantities ordered.
        seller = product_id.with_company(company_id)._select_seller(
            partner_id=partner,
            quantity=uom_po_qty,
            date=po.date_order and po.date_order.date(),
            uom_id=product_id.uom_po_id)

        product_taxes = product_id.supplier_taxes_id.filtered(lambda x: x.company_id.id == company_id.id)
        taxes = po.fiscal_position_id.map_tax(product_taxes)

        price_unit = self.env['account.tax']._fix_tax_included_price_company(
            seller.price, product_taxes, taxes, company_id) if seller else 0.0
        if price_unit and seller and po.currency_id and seller.currency_id != po.currency_id:
            price_unit = seller.currency_id._convert(
                price_unit, po.currency_id, po.company_id, po.date_order or fields.Date.today())

        product_lang = product_id.with_prefetch().with_context(
            lang=partner.lang,
            partner_id=partner.id,
        )
        name = product_lang.with_context(seller_id=seller.id).display_name
        if product_lang.description_purchase:
            name += '\n' + product_lang.description_purchase

        date_planned = self.order_id.date_planned or self._get_date_planned(seller, po=po)

        return {
            'name': name,
            'product_qty': uom_po_qty,
            'product_id': product_id.id,
            'product_uom_id': product_id.uom_po_id.id,
            'price_unit': price_unit,
            'date_planned': date_planned,
            'order_id': po.id,
        }

    def _convert_to_middle_of_day(self, date):
        """Return a datetime which is the noon of the input date(time) according
        to order user's time zone, convert to UTC time.
        """
        return timezone(self.order_id.user_id.tz or self.company_id.partner_id.tz or 'UTC').localize(
            datetime.combine(date, time(12))).astimezone(UTC).replace(tzinfo=None)

    def _update_date_planned(self, updated_date):
        self.date_planned = updated_date

    def _track_qty_received(self, new_qty):
        self.ensure_one()
        if new_qty != self.qty_received and self.order_id.state == 'subscribed':
            self.order_id.message_post_with_view(
                'purchase.track_po_line_qty_received_template',
                values={'line': self, 'qty_received': new_qty},
                subtype_id=self.env.ref('mail.mt_note').id
            )

    @api.depends('product_packaging_qty')
    def _compute_product_qty(self):
        for line in self:
            if line.product_packaging_id:
                packaging_uom = line.product_packaging_id.product_uom_id
                qty_per_packaging = line.product_packaging_id.qty
                product_qty = packaging_uom._compute_quantity(line.product_packaging_qty * qty_per_packaging,
                                                              line.product_uom_id)
                if float_compare(product_qty, line.product_qty, precision_rounding=line.product_uom_id.rounding) != 0:
                    line.product_qty = product_qty

    @api.depends('product_uom_id', 'product_qty', 'product_id.uom_id')
    def _compute_product_uom_qty(self):
        for line in self:
            if line.product_id and line.product_id.uom_id != line.product_uom_id:
                line.product_uom_qty = line.product_uom_id._compute_quantity(line.product_qty, line.product_id.uom_id)
            else:
                line.product_uom_qty = line.product_qty

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

    @api.depends('product_packaging_id', 'product_uom_id', 'product_qty')
    def _compute_product_packaging_qty(self):
        for line in self:
            if not line.product_packaging_id:
                line.product_packaging_qty = 0
            else:
                packaging_uom = line.product_packaging_id.product_uom_id
                packaging_uom_qty = line.product_uom_id._compute_quantity(line.product_qty, packaging_uom)
                line.product_packaging_qty = float_round(packaging_uom_qty / line.product_packaging_id.qty,
                                                         precision_rounding=packaging_uom.rounding)

    @api.depends('product_packaging_qty')
    def _compute_product_qty(self):
        for line in self:
            if line.product_packaging_id:
                packaging_uom = line.product_packaging_id.product_uom_id
                qty_per_packaging = line.product_packaging_id.qty
                product_qty = packaging_uom._compute_quantity(line.product_packaging_qty * qty_per_packaging,
                                                              line.product_uom_id)
                if float_compare(product_qty, line.product_qty, precision_rounding=line.product_uom_id.rounding) != 0:
                    line.product_qty = product_qty

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
                line.product_packaging_id = line.product_id.packaging_ids.filtered(
                    'purchase')._find_suitable_product_packaging(line.product_qty,
                                                                 line.product_uom_id) or line.product_packaging_id

    @api.depends('product_uom_id', 'product_qty', 'product_id.uom_id')
    def _compute_product_uom_qty(self):
        for line in self:
            if line.product_id and line.product_id.uom_id != line.product_uom_id:
                line.product_uom_qty = line.product_uom_id._compute_quantity(line.product_qty, line.product_id.uom_id)
            else:
                line.product_uom_qty = line.product_qty

    def action_purchase_history(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("purchase.action_purchase_history")
        action['domain'] = [('state', 'in', ['purchase', 'done']), ('product_id', '=', self.product_id.id)]
        action['display_name'] = _("Purchase History for %s", self.product_id.display_name)
        action['context'] = {
            'search_default_partner_id': self.order_id.partner_id.id
        }

        return action

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

    def _suggest_quantity(self):
        '''
        Suggest a minimal quantity based on the seller
        '''
        if not self.product_id:
            return
        seller_min_qty = self.product_id.seller_ids \
            .filtered(lambda r: r.partner_id == self.order_id.partner_id and (
                    not r.product_id or r.product_id == self.product_id)) \
            .sorted(key=lambda r: r.min_qty)
        if seller_min_qty:
            self.product_qty = seller_min_qty[0].min_qty or 1.0
            self.product_uom = seller_min_qty[0].product_uom
        else:
            self.product_qty = 1.0

    def _product_id_change(self):
        if not self.product_id:
            return

        # TODO: Remove when onchanges are replaced with computes
        if not (self.env.context.get(
                'origin_po_id') and self.product_uom_id and self.product_id.uom_id.category_id == self.product_uom_category_id):
            self.product_uom_id = self.product_id.uom_po_id or self.product_id.uom_id
        product_lang = self.product_id.with_context(
            lang=get_lang(self.env, self.order_id.partner_id.lang).code,
            partner_id=self.order_id.partner_id.id,
            company_id=self.company_id.id,
        )
        self.name = self._get_product_purchase_description(product_lang)

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

    @api.depends('product_qty', 'product_uom_id')
    def _compute_price_unit_and_date_planned_and_name(self):
        for line in self:
            if not line.product_id:
                continue
            params = {'order_id': line.order_id}
            seller = line.product_id._select_seller(
                partner_id=line.order_id.partner_id,
                quantity=line.product_qty,
                date=line.order_id.date_order,
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
                    line.date,
                    False
                )
                line.price_unit = float_round(price_unit, precision_digits=max(line.currency_id.decimal_places,
                                                                               self.env[
                                                                                   'decimal.precision'].precision_get(
                                                                                   'Product Price')))
                continue

            price_unit = line.env['account.tax']._fix_tax_included_price_company(seller.price,
                                                                                 line.product_id.supplier_taxes_id,
                                                                                 line.taxes_id,
                                                                                 line.company_id) if seller else 0.0
            price_unit = seller.currency_id._convert(price_unit, line.currency_id, line.company_id, line.date,
                                                     False)
            price_unit = float_round(price_unit, precision_digits=max(line.currency_id.decimal_places,
                                                                      self.env['decimal.precision'].precision_get(
                                                                          'Product Price')))
            line.price_unit = seller.product_uom_id._compute_price(price_unit, line.product_uom_id)

            # record product names to avoid resetting custom descriptions
            default_names = []
            vendors = line.product_id._prepare_sellers({})
            for vendor in vendors:
                product_ctx = {'seller_id': vendor.id, 'lang': get_lang(line.env, line.order_id.partner_id.lang).code}
                default_names.append(line._get_product_purchase_description(line.product_id.with_context(product_ctx)))
            if not line.name or line.name in default_names:
                product_ctx = {'seller_id': seller.id, 'lang': get_lang(line.env, line.order_id.partner_id.lang).code}
                line.name = line._get_product_purchase_description(line.product_id.with_context(product_ctx))

    def _get_product_purchase_description(self, product_lang):
        self.ensure_one()
        name = product_lang.display_name
        if product_lang.description_purchase:
            name += '\n' + product_lang.description_purchase

        return name

    def _prepare_account_move_line(self, move=False, ):
        self.ensure_one()
        aml_currency = move and move.currency_id or self.currency_id
        date = move and move.date or fields.Date.today()
        res = {
            'account_id': '',
            'product_id': self.product_id.id,
            'product_uom_id': self.product_uom_id.id,
            'display_type': self.display_type or 'product',
            'name': '%s: %s - %s' % (self.order_id.name, self.name, self.order_id.short_name),
            'quantity': self.product_qty,
            'partner_id': self.order_id.partner_id,
            'price_unit': self.currency_id._convert(self.price_unit, aml_currency, self.company_id, date, round=False),
            # 'tax_ids': [(6, 0, self.taxes_id.ids)],
            'suscription_product_line_id': self.id,
            'date_maturity': self.date_maturity,
        }
        return res

    def _prepare_account_move_line_integration(self, move=False,):
        self.ensure_one()
        aml_currency = move and move.currency_id or self.currency_id
        date = move and move.date or fields.Date.today()
        # Si la contabilifaf anglosajona esta activada
        if self.product_id.product_tmpl_id.categ_id.property_valuation=='real_time':
            account_id=self.product_id.product_tmpl_id.get_product_accounts()['forecast_integration_account'].id \
                       or self.product_id.product_tmpl_id.categ_id.forecast_integration_account.id \
                        or self.company_id.forecast_integration_account.id or \
                        self.env['account.account'].search(domain=[('account_type','=','liability_payable_forecast'),
                        ('deprecated', '=', False),
                        ('company_id', '=', self.env.company.id)], limit=1).id
        else:
            account_id=self.product_id.product_tmpl_id.get_product_accounts()['expense'].id \
                       or self.product_id.product_tmpl_id.categ_id.property_account_expense_categ_id.id \
                        or self.env['account.account'].search(domain=[('account_type','=','expense'),
                        ('deprecated', '=', False),
                        ('company_id', '=', self.env.company.id)], limit=1).id
        res = {
            'account_id': account_id,
            'display_type': self.display_type or 'product',
            'name': '%s: %s - %s' % (self.order_id.name, self.name, self.order_id.short_name),
            'partner_id': self.order_id.partner_id,
            'debit': self.currency_id._convert(self.price_unit, aml_currency, self.company_id, date, round=False),
            # 'tax_ids': [(6, 0, self.taxes_id.ids)],
            'integration_cash_line_id': self.id,
            'date_maturity': self.date_maturity,
        }
        return res
    # low level methods

    @api.model
    def create(self, vals):
        if vals.get('short_name', _('New')) == _('New'):
            seq_date = None
            if 'date' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date']))
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'account.suscription.product.line', sequence_date=seq_date) or _('New')
        return super().create(vals)


class SuscriptionOrder(models.Model):
    _name = 'account.suscription.order'
    _inherit = 'account.suscription.order'

    cash_lines = fields.One2many(string='Cash Lines', comodel_name='account.suscription.cash.line',
                                 inverse_name='order_id',
                                 copy=False,
                                 readonly=False,
                                 help='Cash Lines Availables')
    credit_lines = fields.One2many(string='Credit Lines', comodel_name='account.suscription.credit.line',
                                   inverse_name='order_id',
                                   copy=False,
                                   readonly=False,
                                   help='Credit Lines Availables')
    product_lines = fields.One2many(string='Product Lines', comodel_name='account.suscription.product.line',
                                    inverse_name='order_id',
                                    copy=False,
                                    readonly=False,
                                    help='Product Lines Availables')
    amount_total = fields.Monetary(string='Total', currency_field='company_currency_id', compute='_compute_totals',)
    # Total Fields
    cash_total = fields.Monetary(string='Cash Total', store=True, readonly=True, compute='_compute_totals',
                                 currency_field='company_currency_id',
                                 help='Resulting Total of the Cash lines to be subscribed, in company currency')
    credit_total = fields.Monetary(string='Credit Total', store=True, readonly=True, compute='_compute_totals',
                                   currency_field='company_currency_id',
                                   help='Resulting Total of the Credit lines to be subscribed, in company currency')
    product_total = fields.Monetary(string='Product Total', store=True, readonly=True, compute='_compute_totals',
                                    currency_field='company_currency_id',
                                    help='Resulting Total of the Product lines to be subscribed, in company currency')

    @api.depends('product_lines.date_planned')
    def _compute_date_planned(self):
        """ date_planned = the earliest date_planned across all order lines. """
        for order in self:
            dates_list = order.product_lines.filtered(lambda x: not x.display_type and x.date_planned).mapped(
                'date_planned')
            if dates_list:
                order.date_planned = min(dates_list)
            else:
                order.date_planned = False

    @api.depends('cash_lines', 'credit_lines', 'product_lines')
    def _compute_totals(self):
        if not self.ids:
            return
        for order in self:
            cash_total = 0
            credit_total = 0
            product_total = 0
            amount_total=0
            cash_lines = order.env['account.suscription.cash.line'].search_read(
                domain=[('order_id', '=', order.id)],
                fields=['price_total']
            )
            credit_lines = order.env['account.suscription.credit.line'].search_read(
                domain=[('order_id', '=', order.id)],
                fields=['price_total']
            )
            product_lines = order.env['account.suscription.product.line'].search_read(
                domain=[('order_id', '=', order.id)],
                fields=['price_total']
            )

            if all([len(cash_lines) > 0, len(cash_lines) > 0, len(product_lines) > 0]):
                cash_total = sum([line['price_total'] for line in cash_lines])
                credit_total = sum([line['price_total'] for line in credit_lines])
                product_total = sum([line['price_total'] for line in product_lines])

            order.cash_total = cash_total
            order.credit_total = credit_total
            order.product_total = product_total
            amount_total=cash_total+credit_total+product_total

    @api.onchange('amount_total')
    def _onchange_amount_total(self):
        for record in self:
            if record.amount_total < record.price_total:
                return {
                    'warning': {'title': "Warning",
                                'message': "The total amount of the lines to be subscribed is less than the value of shares to be acquired. Any difference will be compensated in cash",
                                'type': 'notification'},
                }

    @api.constrains('price_total', 'product_total', 'credit_total', 'cash_total')
    def _check_total_amount(self):
        for rec in self:
            if rec.price_total < (rec.product_total + rec.credit_total + rec.cash_total):
                raise ValidationError(
                    _('The total amount of the lines to be subscribed must coincide with the total of the shares acquired'))

    @api.onchange('date_planned')
    def onchange_date_planned(self):
        if self.date_planned:
            self.product_lines.filtered(lambda line: not line.display_type).date_planned = self.date_planned
