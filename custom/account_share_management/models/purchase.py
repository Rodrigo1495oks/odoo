# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from itertools import groupby

from time import time
from dateutil import relativedelta
from pytz import timezone, UTC
from markupsafe import escape, Markup
from datetime import datetime
from werkzeug.urls import url_encode
from odoo.tools.float_utils import float_is_zero, float_compare, float_round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, format_amount, format_date, formatLang, get_lang, groupby
from odoo import models, fields, api


from odoo.exceptions import ValidationError
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tools.translate import _

from odoo.exceptions import UserError

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    share_issuance=fields.Many2one(string='Orden de Emisión', comodel_name='account.share.issuance', readonly=True, help='Emisión de Acciones Relacionada')

# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo import models, fields, api, tools
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError, ValidationError


class SharesIssuance(models.Model):
    _inherit = 'account.share.issuance'
    
    share_cost = fields.One2many(
        string='Costos de Emisión', comodel_name='purchase.order', inverse_name='share_issuance', readonly=True)