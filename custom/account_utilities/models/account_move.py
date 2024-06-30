# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from bisect import bisect_left
from collections import defaultdict

class AccountMove(models.Model):
    _inherit = "account.move"

    move_type = fields.Selection(
        selection_add=[
            ('subscription', 'Suscription'),
            ('integration', 'Integration'),
            ('contribution', 'Aporte Irrevocable'),
            ('redemption', 'Rescate de Acciones'),
            ('share_sale', 'Venta de Acciones'),
            ('reduction', 'Reducción de Capital'),
            ('certificate', 'Emision de Bonos'),
            ('certificate_line', 'Líneas de Bonos'),
            ('certificate_refund', 'Reintegro de Bonos'),
            ('issue_premium_cancelation', 'Cancelación de Primas')
        ], ondelete = {
        'subscription':  lambda recs: recs.write({'move_type': 'entry' }),
        'integration':  lambda recs: recs.write({'move_type': 'entry' }),
        'contribution':  lambda recs: recs.write({'move_type': 'entry' }),
        'redemption':  lambda recs: recs.write({'move_type': 'entry' }),
        'share_sale':  lambda recs: recs.write({'move_type': 'entry' }),
        'reduction':  lambda recs: recs.write({'move_type': 'entry' }),
        'certificate':  lambda recs: recs.write({'move_type': 'entry' }),
        'certificate_line':  lambda recs: recs.write({'move_type': 'entry' }),
        'certificate_refund':  lambda recs: recs.write({'move_type': 'entry' }),
        'issue_premium_cancelation':  lambda recs: recs.write({'move_type': 'entry' }),
        }
    )