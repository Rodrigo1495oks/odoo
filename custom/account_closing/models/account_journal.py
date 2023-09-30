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
        ('end_of_year','Cierre de Ejercicio'),
    ])