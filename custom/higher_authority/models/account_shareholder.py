# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import collections
import hashlib
import re
import pytz
import requests
from odoo.exceptions import UserError
from werkzeug import urls
from odoo.tools.translate import _

from datetime import datetime, timedelta

from odoo.tools.float_utils import float_is_zero, float_compare

from odoo import models, fields, api, tools
from odoo.osv.expression import get_unaccent_wrapper

from odoo.exceptions import ValidationError

# Global variables used for the warning fields declared on the res.partner
# in the following modules : sale, purchase, account, stock
WARNING_MESSAGE = [
    ('no-message', 'No Message'),
    ('warning', 'Warning'),
    ('block', 'Blocking Message')
]
WARNING_HELP = 'Selecting the "Warning" option will notify user with the message, Selecting "Blocking Message" will throw an exception with the message and block the flow. The Message has to be written in the next field.'


ADDRESS_FIELDS = ('street', 'street2', 'zip', 'city', 'state_id', 'country_id')


@api.model
def _lang_get(self):
    return self.env['res.lang'].get_installed()


# put POSIX 'Etc/*' entries at the end to avoid confusing users - see bug 1086728
_tzs = [(tz, tz) for tz in sorted(pytz.all_timezones,
                                  key=lambda tz: tz if not tz.startswith('Etc/') else '_')]


def _tz_get(self):
    return _tzs


class AccountShareholder(models.Model):
    _name = 'account.shareholder'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _inherits = {'res.partner': 'partner_id'}
    _description = 'Objeto Accionista'
    # _order = 'short_name desc'
    # _rec_name = 'short_name'
    partner_id = fields.Many2one(comodel_name='res.partner',
                                 required=True, ondelete='cascade', readonly=True, index=True, store=True)

    def _default_category(self):
        return self.env['res.partner.category'].browse(self._context.get('category_id'))

    @api.model
    def default_get(self, default_fields):
        """Add the company of the parent as default if we are creating a child partner.
        Also take the parent lang by default if any, otherwise, fallback to default DB lang."""
        values = super().default_get(default_fields)
        parent = self.env["res.partner"]
        if 'parent_id' in default_fields and values.get('parent_id'):
            parent = self.browse(values.get('parent_id'))
            values['company_id'] = parent.company_id.id
        if 'lang' in default_fields:
            values['lang'] = values.get('lang') or parent.lang or self.env.lang
        return values

    start_date = fields.Datetime(
        string='Fecha Inicio del cargo', readonly=True)
    end_date = fields.Datetime(string='Fecha de Finalización', readonly=True)
    date_of_birth = fields.Date(string='Fecha de Nacimiento', readonly=True)
    post_code = fields.Integer(string='Código Postal')
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Urgent')], 'Priority', default='0', index=True)

    # campos relacionales
    position = fields.Many2one(
        string='Cargo', help='Cargo del accionista dentro de la asamblea', comodel_name='account.shareholder.position')
    shares = fields.One2many(string='Acciones', comodel_name='account.share',
                             inverse_name='shareholder', store=True, help='Acciones que le pertenecen a este acconista')

    # contabilidad
    bank_account_id = fields.Many2one('res.partner.bank',
                                      string="Bank Account",
                                      ondelete='restrict', copy=False,
                                      check_company=True,
                                      domain="[('partner_id','=', company_partner_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    bank_id = fields.Many2one(
        'res.bank', related='bank_account_id.bank_id', readonly=False)
    property_account_shareholding_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Cuenta de Acciones",
                                                       domain="[('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Esta cuenta será usada para las suscripciones e integraciones del accionista, a pesar que sea establecida una cuenta por defecto diferente",
                                                       required=True)
    property_account_subscription_id=fields.Many2one('account.account', company_dependent=True,
                                                       string="Cuenta de Acciones",
                                                       domain="[('internal_type', '=', 'receivable'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                       help="Esta cuenta será usada para las suscripciones e integraciones del accionista, a pesar que sea establecida una cuenta por defecto diferente",
                                                       required=True)
    # pagos
    property_shareholder_payment_term_id = fields.Many2one('account.payment.term', company_dependent=True,
                                                           string='Vendor Payment Terms',
                                                           domain="[('company_id', 'in', [current_company_id, False])]",
                                                           help="Este termino de pago será usado para fijar los plazos limite para realizar los aportes")

    property_payment_method_id = fields.Many2one(
        comodel_name='account.payment.method',
        string='Métodos de Pago',
        company_dependent=True,
        domain="[('payment_type', '=', 'inbound')]",
        help="Método de pago preferido"
    )

    property_sharehold_currency_id = fields.Many2one(
        'res.currency', string="Móneda de las acciones", company_dependent=True,
        help="Esta moneda será usada en lugar de la moneda por defecto para los asiento contables")

    # Inventario

    property_stock_shareholder = fields.Many2one(
        'stock.location', string="Ubicación de Accionista", company_dependent=True, check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', allowed_company_ids[0])]",
        help="La localizacion usada como origen para este accionista.")

    @api.depends('is_company', 'name', 'parent_id.display_name', 'type', 'company_name')
    def _compute_display_name(self):
        diff = dict(show_address=None, show_address_only=None,
                    show_email=None, html_format=None, show_vat=None)
        names = dict(self.with_context(**diff).name_get())
        for partner in self:
            partner.display_name = names.get(partner.id)

    @api.depends('lang')
    def _compute_active_lang_count(self):
        lang_count = len(self.env['res.lang'].get_installed())
        for partner in self:
            partner.active_lang_count = lang_count

    @api.depends('tz')
    def _compute_tz_offset(self):
        for partner in self:
            partner.tz_offset = datetime.datetime.now(
                pytz.timezone(partner.tz or 'GMT')).strftime('%z')

    @api.depends('user_ids.share', 'user_ids.active')
    def _compute_partner_share(self):
        super_partner = self.env['res.users'].browse(SUPERUSER_ID).partner_id
        if super_partner in self:
            super_partner.partner_share = False
        for partner in self - super_partner:
            partner.partner_share = not partner.user_ids or not any(
                not user.share for user in partner.user_ids)

    @api.depends('vat', 'company_id')
    def _compute_same_vat_partner_id(self):
        for partner in self:
            # use _origin to deal with onchange()
            partner_id = partner._origin.id
            # active_test = False because if a partner has been deactivated you still want to raise the error,
            # so that you can reactivate it instead of creating a new one, which would loose its history.
            AccountShareholder = self.with_context(active_test=False).sudo()
            domain = [
                ('vat', '=', partner.vat),
                ('company_id', 'in', [False, partner.company_id.id]),
            ]
            if partner_id:
                domain += [('id', '!=', partner_id), '!',
                           ('id', 'child_of', partner_id)]
            partner.same_vat_partner_id = bool(
                partner.vat) and not partner.parent_id and AccountShareholder.search(domain, limit=1)

    @api.depends(lambda self: self._display_address_depends())
    def _compute_contact_address(self):
        for partner in self:
            partner.contact_address = partner._display_address()

    def _compute_get_ids(self):
        for partner in self:
            partner.self = partner.id

    @api.depends('is_company', 'parent_id.commercial_partner_id')
    def _compute_commercial_partner(self):
        for partner in self:
            if partner.is_company or not partner.parent_id:
                partner.commercial_partner_id = partner
            else:
                partner.commercial_partner_id = partner.parent_id.commercial_partner_id

    @api.depends('company_name', 'parent_id.is_company', 'commercial_partner_id.name')
    def _compute_commercial_company_name(self):
        for partner in self:
            p = partner.commercial_partner_id
            partner.commercial_company_name = p.is_company and p.name or partner.company_name

    @api.model
    def _fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        if (not view_id) and (view_type == 'form') and self._context.get('force_email'):
            view_id = self.env.ref('base.view_partner_simple_form').id
        res = super(AccountShareholder, self)._fields_view_get(view_id=view_id,
                                                               view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            res['arch'] = self._fields_view_get_address(res['arch'])
        return res

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(
                _('You cannot create recursive AccountShareholder hierarchies.'))

    def copy(self, default=None):
        self.ensure_one()
        chosen_name = default.get('name') if default else ''
        new_name = chosen_name or _('%s (copy)', self.name)
        default = dict(default or {}, name=new_name)
        return super(AccountShareholder, self).copy(default)

    @api.onchange('parent_id')
    def onchange_parent_id(self):
        # return values in result, as this method is used by _fields_sync()
        if not self.parent_id:
            return
        result = {}
        partner = self._origin
        if partner.parent_id and partner.parent_id != self.parent_id:
            result['warning'] = {
                'title': _('Warning'),
                'message': _('Changing the company of a contact should only be done if it '
                             'was never correctly set. If an existing contact starts working for a new '
                             'company then a new contact should be created under that new '
                             'company. You can use the "Discard" button to abandon this change.')}
        if partner.type == 'contact' or self.type == 'contact':
            # for contacts: copy the parent address, if set (aka, at least one
            # value is set in the address: otherwise, keep the one from the
            # contact)
            address_fields = self._address_fields()
            if any(self.parent_id[key] for key in address_fields):
                def convert(value):
                    return value.id if isinstance(value, models.BaseModel) else value
                result['value'] = {key: convert(
                    self.parent_id[key]) for key in address_fields}
        return result

    @api.onchange('parent_id')
    def _onchange_parent_id_for_lang(self):
        # While creating / updating child contact, take the parent lang by default if any
        # otherwise, fallback to default context / DB lang
        if self.parent_id:
            self.lang = self.parent_id.lang or self.env.context.get(
                'default_lang') or self.env.lang

    @api.onchange('country_id')
    def _onchange_country_id(self):
        if self.country_id and self.country_id != self.state_id.country_id:
            self.state_id = False

    @api.onchange('state_id')
    def _onchange_state(self):
        if self.state_id.country_id:
            self.country_id = self.state_id.country_id

    @api.onchange('email')
    def onchange_email(self):
        if not self.image_1920 and self._context.get('gravatar_image') and self.email:
            self.image_1920 = self._get_gravatar_image(self.email)

    @api.onchange('parent_id', 'company_id')
    def _onchange_company_id(self):
        if self.parent_id:
            self.company_id = self.parent_id.company_id.id

    @api.depends('name', 'email')
    def _compute_email_formatted(self):
        for partner in self:
            if partner.email:
                partner.email_formatted = tools.formataddr(
                    (partner.name or u"False", partner.email or u"False"))
            else:
                partner.email_formatted = ''

    @api.depends('is_company')
    def _compute_company_type(self):
        for partner in self:
            partner.company_type = 'company' if partner.is_company else 'person'

    def _write_company_type(self):
        for partner in self:
            partner.is_company = partner.company_type == 'company'

    @api.onchange('company_type')
    def onchange_company_type(self):
        self.is_company = (self.company_type == 'company')

    @api.constrains('barcode')
    def _check_barcode_unicity(self):
        if self.barcode and self.env['res.partner'].search_count([('barcode', '=', self.barcode)]) > 1:
            raise ValidationError('An other user already has this barcode')

    def _update_fields_values(self, fields):
        """ Returns dict of write() values for synchronizing ``fields`` """
        values = {}
        for fname in fields:
            field = self._fields[fname]
            if field.type == 'many2one':
                values[fname] = self[fname].id
            elif field.type == 'one2many':
                raise AssertionError(
                    _('One2Many fields cannot be synchronized as part of `commercial_fields` or `address fields`'))
            elif field.type == 'many2many':
                values[fname] = [(6, 0, self[fname].ids)]
            else:
                values[fname] = self[fname]
        return values

    @api.model
    def _address_fields(self):
        """Returns the list of address fields that are synced from the parent."""
        return list(ADDRESS_FIELDS)

    @api.model
    def _formatting_address_fields(self):
        """Returns the list of address fields usable to format addresses."""
        return self._address_fields()

    def update_address(self, vals):
        addr_vals = {key: vals[key]
                     for key in self._address_fields() if key in vals}
        if addr_vals:
            return super(AccountShareholder, self).write(addr_vals)

    @api.model
    def _commercial_fields(self):
        """ Returns the list of fields that are managed by the commercial entity
        to which a partner belongs. These fields are meant to be hidden on
        partners that aren't `commercial entities` themselves, and will be
        delegated to the parent `commercial entity`. The list is meant to be
        extended by inheriting classes. """
        return ['vat', 'credit_limit']

    def _commercial_sync_from_company(self):
        """ Handle sync of commercial fields when a new parent commercial entity is set,
        as if they were related fields """
        commercial_partner = self.commercial_partner_id
        if commercial_partner != self:
            sync_vals = commercial_partner._update_fields_values(
                self._commercial_fields())
            self.write(sync_vals)

    def _commercial_sync_to_children(self):
        """ Handle sync of commercial fields to descendants """
        commercial_partner = self.commercial_partner_id
        sync_vals = commercial_partner._update_fields_values(
            self._commercial_fields())
        sync_children = self.child_ids.filtered(lambda c: not c.is_company)
        for child in sync_children:
            child._commercial_sync_to_children()
        res = sync_children.write(sync_vals)
        sync_children._compute_commercial_partner()
        return res

    def _fields_sync(self, values):
        """ Sync commercial fields and address fields from company and to children after create/update,
        just as if those were all modeled as fields.related to the parent """
        # 1. From UPSTREAM: sync from parent
        if values.get('parent_id') or values.get('type') == 'contact':
            # 1a. Commercial fields: sync if parent changed
            if values.get('parent_id'):
                self._commercial_sync_from_company()
            # 1b. Address fields: sync if parent or use_parent changed *and* both are now set
            if self.parent_id and self.type == 'contact':
                onchange_vals = self.onchange_parent_id().get('value', {})
                self.update_address(onchange_vals)

        # 2. To DOWNSTREAM: sync children
        self._children_sync(values)

    def _children_sync(self, values):
        if not self.child_ids:
            return
        # 2a. Commercial Fields: sync if commercial entity
        if self.commercial_partner_id == self:
            commercial_fields = self._commercial_fields()
            if any(field in values for field in commercial_fields):
                self._commercial_sync_to_children()
        for child in self.child_ids.filtered(lambda c: not c.is_company):
            if child.commercial_partner_id != self.commercial_partner_id:
                self._commercial_sync_to_children()
                break
        # 2b. Address fields: sync if address changed
        address_fields = self._address_fields()
        if any(field in values for field in address_fields):
            contacts = self.child_ids.filtered(lambda c: c.type == 'contact')
            contacts.update_address(values)

    def _handle_first_contact_creation(self):
        """ On creation of first contact for a company (or root) that has no address, assume contact address
        was meant to be company address """
        parent = self.parent_id
        address_fields = self._address_fields()
        if (parent.is_company or not parent.parent_id) and len(parent.child_ids) == 1 and \
                any(self[f] for f in address_fields) and not any(parent[f] for f in address_fields):
            addr_vals = self._update_fields_values(address_fields)
            parent.update_address(addr_vals)

    def _clean_website(self, website):
        url = urls.url_parse(website)
        if not url.scheme:
            if not url.netloc:
                url = url.replace(netloc=url.path, path='')
            website = url.replace(scheme='http').to_url()
        return website

    def write(self, vals):
        if vals.get('active') is False:
            # DLE: It should not be necessary to modify this to make work the ORM. The problem was just the recompute
            # of partner.user_ids when you create a new user for this partner, see test test_70_archive_internal_partners
            # You modified it in a previous commit, see original commit of this:
            # https://github.com/odoo/odoo/commit/9d7226371730e73c296bcc68eb1f856f82b0b4ed
            #
            # RCO: when creating a user for partner, the user is automatically added in partner.user_ids.
            # This is wrong if the user is not active, as partner.user_ids only returns active users.
            # Hence this temporary hack until the ORM updates inverse fields correctly.
            self.invalidate_cache(['user_ids'], self._ids)
            for partner in self:
                if partner.active and partner.user_ids:
                    raise ValidationError(
                        _('You cannot archive a contact linked to a portal or internal user.'))
        # res.partner must only allow to set the company_id of a partner if it
        # is the same as the company of all users that inherit from this partner
        # (this is to allow the code from res_users to write to the partner!) or
        # if setting the company_id to False (this is compatible with any user
        # company)
        if vals.get('website'):
            vals['website'] = self._clean_website(vals['website'])
        if vals.get('parent_id'):
            vals['company_name'] = False
        if 'company_id' in vals:
            company_id = vals['company_id']
            for partner in self:
                if company_id and partner.user_ids:
                    company = self.env['res.company'].browse(company_id)
                    companies = set(
                        user.company_id for user in partner.user_ids)
                    if len(companies) > 1 or company not in companies:
                        raise UserError(
                            ("The selected company is not compatible with the companies of the related user(s)"))
                if partner.child_ids:
                    partner.child_ids.write({'company_id': company_id})
        result = True
        # To write in SUPERUSER on field is_company and avoid access rights problems.
        if 'is_company' in vals and self.user_has_groups('base.group_partner_manager') and not self.env.su:
            result = super(AccountShareholder, self.sudo()).write(
                {'is_company': vals.get('is_company')})
            del vals['is_company']
        result = result and super(AccountShareholder, self).write(vals)
        for partner in self:
            if any(u.has_group('base.group_user') for u in partner.user_ids if u != self.env.user):
                self.env['res.users'].check_access_rights('write')
            partner._fields_sync(vals)
        return result

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('import_file'):
            self._check_import_consistency(vals_list)
        for vals in vals_list:
            if vals.get('website'):
                vals['website'] = self._clean_website(vals['website'])
            if vals.get('parent_id'):
                vals['company_name'] = False
        partners = super(AccountShareholder, self).create(vals_list)

        if self.env.context.get('_partners_skip_fields_sync'):
            return partners

        for partner, vals in zip(partners, vals_list):
            partner._fields_sync(vals)
            # Lang: propagate from parent if no value was given
            if 'lang' not in vals and partner.parent_id:
                partner._onchange_parent_id_for_lang()
            partner._handle_first_contact_creation()
        return partners

    def _load_records_create(self, vals_list):
        partners = super(AccountShareholder, self.with_context(
            _partners_skip_fields_sync=True))._load_records_create(vals_list)

        # batch up first part of _fields_sync
        # group partners by commercial_partner_id (if not self) and parent_id (if type == contact)
        groups = collections.defaultdict(list)
        for partner, vals in zip(partners, vals_list):
            cp_id = None
            if vals.get('parent_id') and partner.commercial_partner_id != partner:
                cp_id = partner.commercial_partner_id.id

            add_id = None
            if partner.parent_id and partner.type == 'contact':
                add_id = partner.parent_id.id
            groups[(cp_id, add_id)].append(partner.id)

        for (cp_id, add_id), children in groups.items():
            # values from parents (commercial, regular) written to their common children
            to_write = {}
            # commercial fields from commercial partner
            if cp_id:
                to_write = self.browse(cp_id)._update_fields_values(
                    self._commercial_fields())
            # address fields from parent
            if add_id:
                parent = self.browse(add_id)
                for f in self._address_fields():
                    v = parent[f]
                    if v:
                        to_write[f] = v.id if isinstance(
                            v, models.BaseModel) else v
            if to_write:
                self.browse(children).write(to_write)

        # do the second half of _fields_sync the "normal" way
        for partner, vals in zip(partners, vals_list):
            partner._children_sync(vals)
            partner._handle_first_contact_creation()
        return partners

    def create_company(self):
        self.ensure_one()
        if self.company_name:
            # Create parent company
            values = dict(name=self.company_name,
                          is_company=True, vat=self.vat)
            values.update(self._update_fields_values(self._address_fields()))
            new_company = self.create(values)
            # Set new company as my parent
            self.write({
                'parent_id': new_company.id,
                'child_ids': [(1, partner_id, dict(parent_id=new_company.id)) for partner_id in self.child_ids.ids]
            })
        return True

    def open_commercial_entity(self):
        """ Utility method used to add an "Open Company" button in partner views """
        self.ensure_one()
        return {'type': 'ir.actions.act_window',
                'res_model': 'res.partner',
                'view_mode': 'form',
                'res_id': self.commercial_partner_id.id,
                'target': 'current',
                'flags': {'form': {'action_buttons': True}}}

    def open_parent(self):
        """ Utility method used to add an "Open Parent" button in partner views """
        self.ensure_one()
        address_form_id = self.env.ref('base.view_partner_address_form').id
        return {'type': 'ir.actions.act_window',
                'res_model': 'res.partner',
                'view_mode': 'form',
                'views': [(address_form_id, 'form')],
                'res_id': self.parent_id.id,
                'target': 'new',
                'flags': {'form': {'action_buttons': True}}}

    def _get_contact_name(self, partner, name):
        return "%s, %s" % (partner.commercial_company_name or partner.sudo().parent_id.name, name)

    def _get_name(self):
        """ Utility method to allow name_get to be overrided without re-browse the partner """
        partner = self
        name = partner.name or ''

        if partner.company_name or partner.parent_id:
            if not name and partner.type in ['invoice', 'delivery', 'other']:
                name = dict(self.fields_get(['type'])[
                            'type']['selection'])[partner.type]
            if not partner.is_company:
                name = self._get_contact_name(partner, name)
        if self._context.get('show_address_only'):
            name = partner._display_address(without_company=True)
        if self._context.get('show_address'):
            name = name + "\n" + partner._display_address(without_company=True)
        name = name.replace('\n\n', '\n')
        name = name.replace('\n\n', '\n')
        if self._context.get('address_inline'):
            splitted_names = name.split("\n")
            name = ", ".join([n for n in splitted_names if n.strip()])
        if self._context.get('show_email') and partner.email:
            name = "%s <%s>" % (name, partner.email)
        if self._context.get('html_format'):
            name = name.replace('\n', '<br/>')
        if self._context.get('show_vat') and partner.vat:
            name = "%s ‒ %s" % (name, partner.vat)
        return name

    def name_get(self):
        res = []
        for partner in self:
            name = partner._get_name()
            res.append((partner.id, name))
        return res

    def _parse_partner_name(self, text):
        """ Parse partner name (given by text) in order to find a name and an
        email. Supported syntax:

          * Raoul <raoul@grosbedon.fr>
          * "Raoul le Grand" <raoul@grosbedon.fr>
          * Raoul raoul@grosbedon.fr (strange fault tolerant support from df40926d2a57c101a3e2d221ecfd08fbb4fea30e)

        Otherwise: default, everything is set as the name. Starting from 13.3
        returned email will be normalized to have a coherent encoding.
         """
        name, email = '', ''
        split_results = tools.email_split_tuples(text)
        if split_results:
            name, email = split_results[0]

        if email and not name:
            fallback_emails = tools.email_split(text.replace(' ', ','))
            if fallback_emails:
                email = fallback_emails[0]
                name = text[:text.index(email)].replace(
                    '"', '').replace('<', '').strip()

        if email:
            email = tools.email_normalize(email)
        else:
            name, email = text, ''

        return name, email

    @api.model
    def name_create(self, name):
        """ Override of orm's name_create method for partners. The purpose is
            to handle some basic formats to create partners using the
            name_create.
            If only an email address is received and that the regex cannot find
            a name, the name will have the email value.
            If 'force_email' key in context: must find the email address. """
        default_type = self._context.get('default_type')
        if default_type and default_type not in self._fields['type'].get_values(self.env):
            context = dict(self._context)
            context.pop('default_type')
            self = self.with_context(context)
        name, email = self._parse_partner_name(name)
        if self._context.get('force_email') and not email:
            raise UserError(
                _("Couldn't create contact without email address!"))

        create_values = {self._rec_name: name or email}
        if email:  # keep default_email in context
            create_values['email'] = email
        partner = self.create(create_values)
        return partner.name_get()[0]

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        """ Override search() to always show inactive children when searching via ``child_of`` operator. The ORM will
        always call search() with a simple domain of the form [('parent_id', 'in', [ids])]. """
        # a special ``domain`` is set on the ``child_ids`` o2m to bypass this logic, as it uses similar domain expressions
        if len(args) == 1 and len(args[0]) == 3 and args[0][:2] == ('parent_id', 'in') \
                and args[0][2] != [False]:
            self = self.with_context(active_test=False)
        return super(AccountShareholder, self)._search(args, offset=offset, limit=limit, order=order,
                                                       count=count, access_rights_uid=access_rights_uid)

    def _get_name_search_order_by_fields(self):
        return ''

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        self = self.with_user(name_get_uid or self.env.uid)
        # as the implementation is in SQL, we force the recompute of fields if necessary
        self.recompute(['display_name'])
        self.flush()
        if args is None:
            args = []
        order_by_rank = self.env.context.get('res_partner_search_mode')
        if (name or order_by_rank) and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            self.check_access_rights('read')
            where_query = self._where_calc(args)
            self._apply_ir_rules(where_query, 'read')
            from_clause, where_clause, where_clause_params = where_query.get_sql()
            from_str = from_clause if from_clause else 'res_partner'
            where_str = where_clause and (
                " WHERE %s AND " % where_clause) or ' WHERE '

            # search on the name of the contacts and of its company
            search_name = name
            if operator in ('ilike', 'like'):
                search_name = '%%%s%%' % name
            if operator in ('=ilike', '=like'):
                operator = operator[1:]

            unaccent = get_unaccent_wrapper(self.env.cr)

            fields = self._get_name_search_order_by_fields()

            query = """SELECT res_partner.id
                         FROM {from_str}
                      {where} ({email} {operator} {percent}
                           OR {display_name} {operator} {percent}
                           OR {reference} {operator} {percent}
                           OR {vat} {operator} {percent})
                           -- don't panic, trust postgres bitmap
                     ORDER BY {fields} {display_name} {operator} {percent} desc,
                              {display_name}
                    """.format(from_str=from_str,
                               fields=fields,
                               where=where_str,
                               operator=operator,
                               email=unaccent('res_partner.email'),
                               display_name=unaccent(
                                   'res_partner.display_name'),
                               reference=unaccent('res_partner.ref'),
                               percent=unaccent('%s'),
                               vat=unaccent('res_partner.vat'),)

            # for email / display_name, reference
            where_clause_params += [search_name]*3
            # for vat
            where_clause_params += [re.sub('[^a-zA-Z0-9\-\.]+',
                                           '', search_name) or None]
            where_clause_params += [search_name]  # for order by
            if limit:
                query += ' limit %s'
                where_clause_params.append(limit)
            self.env.cr.execute(query, where_clause_params)
            return [row[0] for row in self.env.cr.fetchall()]

        return super(AccountShareholder, self)._name_search(name, args, operator=operator, limit=limit, name_get_uid=name_get_uid)

    @api.model
    @api.returns('self', lambda value: value.id)
    def find_or_create(self, email, assert_valid_email=False):
        """ Find a partner with the given ``email`` or use :py:method:`~.name_create`
        to create a new one.

        :param str email: email-like string, which should contain at least one email,
            e.g. ``"Raoul Grosbedon <r.g@grosbedon.fr>"``
        :param boolean assert_valid_email: raise if no valid email is found
        :return: newly created record
        """
        if not email:
            raise ValueError(
                _('An email is required for find_or_create to work'))

        parsed_name, parsed_email = self._parse_partner_name(email)
        if not parsed_email and assert_valid_email:
            raise ValueError(
                _('A valid email is required for find_or_create to work properly.'))

        partners = self.search([('email', '=ilike', parsed_email)], limit=1)
        if partners:
            return partners

        create_values = {self._rec_name: parsed_name or parsed_email}
        if parsed_email:  # keep default_email in context
            create_values['email'] = parsed_email
        return self.create(create_values)

    def _get_gravatar_image(self, email):
        email_hash = hashlib.md5(email.lower().encode('utf-8')).hexdigest()
        url = "https://www.gravatar.com/avatar/" + email_hash
        try:
            res = requests.get(url, params={'d': '404', 's': '128'}, timeout=5)
            if res.status_code != requests.codes.ok:
                return False
        except requests.exceptions.ConnectionError as e:
            return False
        except requests.exceptions.Timeout as e:
            return False
        return base64.b64encode(res.content)

    def _email_send(self, email_from, subject, body, on_error=None):
        for partner in self.filtered('email'):
            tools.email_send(
                email_from, [partner.email], subject, body, on_error)
        return True

    def address_get(self, adr_pref=None):
        """ Find contacts/addresses of the right type(s) by doing a depth-first-search
        through descendants within company boundaries (stop at entities flagged ``is_company``)
        then continuing the search at the ancestors that are within the same company boundaries.
        Defaults to partners of type ``'default'`` when the exact type is not found, or to the
        provided partner itself if no type ``'default'`` is found either. """
        adr_pref = set(adr_pref or [])
        if 'contact' not in adr_pref:
            adr_pref.add('contact')
        result = {}
        visited = set()
        for partner in self:
            current_partner = partner
            while current_partner:
                to_scan = [current_partner]
                # Scan descendants, DFS
                while to_scan:
                    record = to_scan.pop(0)
                    visited.add(record)
                    if record.type in adr_pref and not result.get(record.type):
                        result[record.type] = record.id
                    if len(result) == len(adr_pref):
                        return result
                    to_scan = [c for c in record.child_ids
                               if c not in visited
                               if not c.is_company] + to_scan

                # Continue scanning at ancestor if current_partner is not a commercial entity
                if current_partner.is_company or not current_partner.parent_id:
                    break
                current_partner = current_partner.parent_id

        # default to type 'contact' or the partner itself
        default = result.get('contact', self.id or False)
        for adr_type in adr_pref:
            result[adr_type] = result.get(adr_type) or default
        return result

    @api.model
    def view_header_get(self, view_id, view_type):
        if self.env.context.get('category_id'):
            return _(
                'AccountShareholders: %(category)s',
                category=self.env['res.partner.category'].browse(
                    self.env.context['category_id']).name,
            )
        return super().view_header_get(view_id, view_type)

    @api.model
    @api.returns('self')
    def main_partner(self):
        ''' Return the main partner '''
        return self.env.ref('base.main_partner')

    @api.model
    def _get_default_address_format(self):
        return "%(street)s\n%(street2)s\n%(city)s %(state_code)s %(zip)s\n%(country_name)s"

    @api.model
    def _get_address_format(self):
        return self.country_id.address_format or self._get_default_address_format()

    def _display_address(self, without_company=False):
        '''
        The purpose of this function is to build and return an address formatted accordingly to the
        standards of the country where it belongs.

        :param address: browse record of the res.partner to format
        :returns: the address formatted in a display that fit its country habits (or the default ones
            if not country is specified)
        :rtype: string
        '''
        # get the information that will be injected into the display format
        # get the address format
        address_format = self._get_address_format()
        args = {
            'state_code': self.state_id.code or '',
            'state_name': self.state_id.name or '',
            'country_code': self.country_id.code or '',
            'country_name': self._get_country_name(),
            'company_name': self.commercial_company_name or '',
        }
        for field in self._formatting_address_fields():
            args[field] = getattr(self, field) or ''
        if without_company:
            args['company_name'] = ''
        elif self.commercial_company_name:
            address_format = '%(company_name)s\n' + address_format
        return address_format % args

    def _display_address_depends(self):
        # field dependencies of method _display_address()
        return self._formatting_address_fields() + [
            'country_id', 'company_name', 'state_id',
        ]

    @api.model
    def get_import_templates(self):
        return [{
            'label': _('Import Template for Customers'),
            'template': '/base/static/xls/res_partner.xls'
        }]

    @api.model
    def _check_import_consistency(self, vals_list):
        """
        The values created by an import are generated by a name search, field by field.
        As a result there is no check that the field values are consistent with each others.
        We check that if the state is given a value, it does belong to the given country, or we remove it.
        """
        States = self.env['res.country.state']
        states_ids = {vals['state_id']
                      for vals in vals_list if vals.get('state_id')}
        state_to_country = States.search(
            [('id', 'in', list(states_ids))]).read(['country_id'])
        for vals in vals_list:
            if vals.get('state_id'):
                country_id = next(
                    c['country_id'][0] for c in state_to_country if c['id'] == vals.get('state_id'))
                state = States.browse(vals['state_id'])
                if state.country_id.id != country_id:
                    state_domain = [('code', '=', state.code),
                                    ('country_id', '=', country_id)]
                    state = States.search(state_domain, limit=1)
                    # replace state or remove it if not found
                    vals['state_id'] = state.id

    def _get_country_name(self):
        return self.country_id.name or ''


class AccountShareholderPosition(models.Model):
    _name = 'account.shareholder.position'
    # _inherits = {'res.partner': 'partner_id'}
    _description = 'Objeto Cargo'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'

    name = fields.Char(string='Nombre')
    short_name = fields.Char(string='Referencia', required=True, index=True)
    active = fields.Boolean(string='Activo', default=True)

    type = fields.Selection(string='Tipo', help='Tipo de Accionista', required=True, selection=[
        ('ordinary', 'Ordinario'),
        ('preferred', 'Preferido'),
        ('founder', 'Fundador')
    ])

    # shares = fields.One2many(string='Acciones', comodel_name='account.share',
    #                          inverse_name='shareholder', store=True, help='Acciones que le pertenecen a este acconista')
