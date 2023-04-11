# -*- coding: utf-8 -*-
# from odoo import http


# class FleetMonitoring(http.Controller):
#     @http.route('/fleet_monitoring/fleet_monitoring', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/fleet_monitoring/fleet_monitoring/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('fleet_monitoring.listing', {
#             'root': '/fleet_monitoring/fleet_monitoring',
#             'objects': http.request.env['fleet_monitoring.fleet_monitoring'].search([]),
#         })

#     @http.route('/fleet_monitoring/fleet_monitoring/objects/<model("fleet_monitoring.fleet_monitoring"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('fleet_monitoring.object', {
#             'object': obj
#         })
