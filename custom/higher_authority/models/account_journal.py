# -*- coding: utf-8 -*-
from odoo import api, Command, fields, models, _
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from odoo.addons.base.models.res_bank import sanitize_account_number
from odoo.tools import remove_accents
import logging
import re

_logger = logging.getLogger(__name__)

def is_encodable_as_ascii(string):
    try:
        remove_accents(string).encode('ascii')
    except UnicodeEncodeError:
        return False
    return True

class AccountJournal(models.Model):
    # _name = "account.journal"
    _inherit='account.journal'

    type = fields.Selection(selection_add=[
            ('integration','Integrations'),
            ('suscription','Subscripctions'),
            ('contribution','Aportes Irrevocables'),
            ('share_sale','Venta de Acciones'),
            ('redemption','Rescate de Acciones'),
            ('payable_amort','Obligaciones Negociables'),
        ], required=True,
        inverse='_inverse_type',
        help="Select 'Sale' for customer invoices journals.\n"\
        "Select 'Purchase' for vendor bills journals.\n"\
        "Select 'Cash' or 'Bank' for journals that are used in customer or vendor payments.\n"\
        "Select 'General' for miscellaneous operations journals.")