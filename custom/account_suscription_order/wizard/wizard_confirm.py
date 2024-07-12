# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import frozendict


class WizardConfirmPartialIntegration(models.TransientModel):
    _name = 'wizard.confirm.partial.integration'
    _description = 'Associate Issuance of shares with issues'

    suscription_order=fields.Many2one(string='Suscription Order', comodel_name='account.suscription.order', ondelete='restrict',readonly=True)

    # Creo la funcion para confirmar la cancelacion total o integracion parcial
    def confirm_partial_integration(self):
        self.ensure_one()
        self.env['account.suscription.order'].browse(self.env.context.get('active_id'))._action_confirm_partial_integration(self.suscription_order)

    def confirm_cancelation(self):
        "Si cancela la orden de suscripcion tengo la opcion de cancelar todas las acciones o de crear una orden de venta de acciones"
        # cuando cree el modulo de venta de acciones, debo heredar y sobrescribir esta acción para habilitar esa caracteristica
        self.ensure_one()
        self.env['account.suscription.order'].browse(
            self.env.context.get('active_id'))._action_confirm_cancel_integration(self.suscription_order)
    @api.model

    def default_get(self, fields_list):
        # OVERRIDE
        res = super().default_get(fields_list)
        if 'suscription_order' in fields_list and 'suscription_order' not in res:
            if self._context.get('active_model') in ['account.suscription.order']:
                res['suscription_order']=self._context.get('suscription_order')
            else:
                raise UserError(_(
                    "This wizard can only be called from a Meeting Subject"
                ))
            return res