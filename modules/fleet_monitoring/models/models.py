# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = "res.company"

    def get_lat_long(self):
        return [self.env.user.company_id.partner_id.partner_latitude,self.env.user.company_id.partner_id.partner_longitude]

class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"
    
    latitude = fields.Float(string='Geo Latitude', digits=(10, 7))
    longitude = fields.Float(string='Geo Longitude', digits=(10, 7))

    def get_map_data(self):
        return self.env['fleet.vehicle'].search_read([],['display_name','latitude','longitude','driver_id'])