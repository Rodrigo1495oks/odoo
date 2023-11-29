# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo.exceptions import UserError
from werkzeug import urls

from datetime import datetime, timedelta


from odoo import models, fields, api, tools


from odoo.exceptions import ValidationError
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tools.translate import _
from odoo.tools.misc import get_lang
from odoo.tools import pycompat
from odoo.exceptions import UserError, AccessError


class AssemblyMeeting(models.Model):
    _name = 'assembly.meeting'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Objeto Reunión de asamblea'
    _order = 'short_name desc'
    _rec_name = 'short_name'
    
    # Compute methods
    @api.depends('partner_ids')
    def _compute_quorum(self):
        for ass in self:
            ass.quorum=len(ass.partner_ids)/(ass.env['res.partner'].filtered(lambda p: len(p.shares)>0)) if len(ass.partner_ids)>0.0 else 0.0
        
    def name_get(self):
        result = []
        for ast in self:
            name = '%s - (%s)' % (ast.name, ast.short_name)
            result.append((ast.id, name))
            return result
        
    @api.depends("date_start", "date_end")
    def _compute_duration(self):
        for rec in self:
            duration = 0.0
            if rec.date_start and rec.date_end:
                start = fields.Datetime.from_string(rec.date_start)
                end = fields.Datetime.from_string(rec.date_end)
                delta = end - start
                duration = delta.total_seconds() / 3600
            rec.duration = duration
    
    @api.depends('state')
    def _compute_available_partner_ids(self):
        """
        Consigue todos los partner que posean al menos 1 accion.
        """
        partner = self.env['res.partner'].search([])
        for am in self:
            am.partner_ids = partner.filtered(
                lambda p: p.shares.ids != []
                )
        
    date_start=fields.Datetime(string='Hora de Inicio', help='Hora de inicio de la reunion')
    date_end=fields.Datetime(string='Hora de Finalización', help='Hora de inicio de la reunion')
    duration = fields.Float(
        string="Actual duration",
        compute=_compute_duration,
        help="Actual duration in hours",
    )
    event_id = fields.One2many(comodel_name='event.event',
                               inverse_name='assembly_meeting',
                               required=False, 
                               ondelete='restrict', 
                               readonly=True, 
                               index=True, 
                               store=True)

    # campos que voy a definir para este modelo en particular
    name = fields.Char(string='Título', 
                       required=True)
    short_name = fields.Char(string='Referencia', 
                             default='New',
                             required=True, 
                             copy=False, 
                             readonly=True)
    assembly_meet_type = fields.Selection(string='Tipo de Asamblea', 
                                          selection=[
        ('ordinary', 'Asamblea Ordinaria'),
        ('extraordinary', 'Asamblea Extraordinaria')
    ])
    description=fields.Text(string='Descripción', 
                            help='Rellene la descripción de la Reunión')
    
    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('finished', 'Finalizada'),
        ('canceled', 'Cancelada')
    ], default='draft')

    topics = fields.One2many(string='Temas a Tratar', 
                             comodel_name='assembly.meeting.topic',
                             inverse_name='assembly_meeting', 
                             store=True, 
                             index=True, 
                             domain="[('state','in','new')]")

    partner_ids = fields.Many2many(string='Accionistas Presentes', 
                                   comodel_name='res.partner',
                                   column1='assembly_meeting', 
                                   column2='partner_id', 
                                   relation='assembly_meeting_partner', compute='_compute_available_partner_ids')
    attendance=fields.One2many(string='Asistencias', 
                               comodel_name='hr.attendance', 
                               help='Control de Asistencias a Reuniones', 
                               inverse_name='assembly_meeting')

    quorum=fields.Float(string='Asistencia',
                         readonly=True, 
                         help='Porcentaje de Asistencia a la Reunión', 
                         compute='_compute_quorum')

    def action_draft(self):
        for meet in self:
            if meet.state not in ['canceled', 'finished']:
                meet.state = 'draft'
            else:
                return UserWarning('No se puede establcer a borrador')

    def action_confirm(self):
        for meet in self:
            if meet.state in ['draft']:
                meet.state = 'new' 
                meet._create_event()
            else:
                return UserWarning('Ya ha sido confirmada previamente')

    def action_finish(self):
        for meet in self:
            if meet.state in ['new']:
                meet.state = 'finished' 
                meet.date_end=fields.Datetime.now()
            else:
                return UserWarning('No se puede finalizar la reunion')
    
    def _create_event(self):
        # Creamos los tickets
        event_vals=self._prepare_event_values()
        # Creamos el ticket
        ticket_vals=self._prepare_ticket_values()
        event_vals['event_ticket_ids'].append((0,0,ticket_vals))
        # Creamos una registración por cada partner
        reg_vals=self._prepare_reg_values()
        for partner in self.partner_ids:
            reg_vals.update({
                'name':'Accionista: %s' %(partner.name),
                'partner_id': partner.id,
                'email':partner.email,
                'mobile':partner.mobile,
                'phone':partner.phone,
                })
            event_vals['registration_ids'].append((0,0, reg_vals))
            new_event= self.env['event.event'].create(event_vals)
        return self.action_view_event(new_event)

    # low level methods

    @api.model
    def create(self, vals):
        if vals.get('short_name', _('New')) == _('New'):
            vals['short_name'] = self.env['ir.sequence'].next_by_code(
                'assembly.meeting') or _('New')
        return super().create(vals)
    def _prepare_event_values(self):
        self.ensure_one()
        return{
            "name":'Reunión Asamblea N° (%s) - (%s)'%(self.short_name, self.name),
            'date_begin': self.date_start,
            'date_end': self.date_end,
            'description':self.description,
            'user_id': self.env.user.id,
            'company_id': self.env.company.id,
            'organizer_id':self.env.company.partner_id.id,
            'seats_max': len(self.env['res.partner'].filtered(lambda p: p.shares.ids != [])),
            'seats_limited': True,
            'ticket_instructions': 'Ticket Correspondiente a una Asamblea de Accionsitas Tipo (%s)'%(self.assembly_meet_type),
            'event_ticket_ids': [],
            'registration_ids': [],
            'assembly_meeting': self.id,
            }
    def _prepare_reg_values(self):
        self.ensure_one()
        return{
            'name':'Accionista: ',
            'event_begin_date': self.date_start,
            'event_end_date': self.date_end,
            'state': 'open',
            'partner_id': '',
            'email':'',
            'mobile':'',
            'phone':'',
            }
    def _prepare_ticket_values(self):
        self.ensure_one()
        return{
            'name':'Ticket Cupo Asamblea N° (%s) de Tipo (%s) - Fecha %s'%(self.short_name, self.assembly_meet_type, self.date_start),
            'description': self.description,
            'seats_max': len(self.env['res.partner'].filtered(lambda p: p.shares.ids != [])),
            'start_sale_datetime': self.date_start-timedelta(days=90),
            'end_sale_datetime':(self.date_start-timedelta(days=90))+timedelta(10)
            }
    def action_view_event(self, events=False):
        """This function returns an action that display existing  events entries of
        given suscription order ids. When only one found, show the events entries
        immediately.
        """
        if not events:
            # Invoice_ids may be filtered depending on the user. To ensure we get all
            # events related to the suscription order, we read them in sudo to fill the00
            # cache.
            self.invalidate_model(['event_id'])
            self.sudo()._read(['event_id'])
            events = self.event_id

        result = self.env['ir.actions.act_window']._for_xml_id(
            'event.action_event_view')
        # choose the view_mode accordingly
        if len(events) > 1:
            result['domain'] = [('id', 'in', events.ids)]
        elif len(events) == 1:
            res = self.env.ref('event.view_event_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in result:
                result['views'] = form_view + \
                    [(state, view)
                     for state, view in result['views'] if view != 'form']
            else:
                result['views'] = form_view
            result['res_id'] = events.id
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result
class AssemblyMeetingTopic(models.Model):
    _inherit = 'assembly.meeting.topic'
    # campos relacionales
    assembly_meeting = fields.Many2one(
        string='Reunion Tratante', 
        comodel_name='assembly.meeting')

class HrAttendance(models.Model):
    _inherit = "hr.attendance"
    assembly_meeting = fields.Many2one(
        string='Reunion Tratante', 
        comodel_name='assembly.meeting', 
        readonly=True)