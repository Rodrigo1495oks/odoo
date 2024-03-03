# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo.exceptions import UserError
from werkzeug import urls

from datetime import datetime, timedelta


from odoo import models, fields, api, tools


from odoo.exceptions import ValidationError
from odoo.osv import expression
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
    
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company.id)
    # Compute methods
    @api.depends('partner_ids')
    def _compute_quorum(self):
        for ass in self:
            if ass.assembly_meet_type!='directory':
                shares=self.env['account.share'].search([])
                total_votes=sum([share.votes_num for share in shares])
                print("_________________________")
                print(total_votes)
                # present_votes=sum([share['votes_num'] for share in [shares for shares in [partner['shares'] for partner in ass.partner_ids]]]) # probemos!!
                nueva_lista=[partner['shares'] for partner in ass.partner_ids]
                present_votes=0
                for shares in nueva_lista:
                    for share in shares:
                        present_votes+=share['votes_num']
                print(present_votes)
                ass.quorum=(present_votes/total_votes) if total_votes>0.0 else 0.0
                
            else:
                present_votes=0

                shares=self.env['account.share'].search([('partner_id.position.type','=','director')])
                total_votes=sum([share.votes_num for share in shares])
                nueva_lista=[partner['shares'] for partner in ass.partner_ids]
                present_votes=0
                for shares in nueva_lista:
                    for share in shares:
                        present_votes+=share['votes_num']
                print(present_votes)
                ass.quorum=(present_votes/total_votes) if total_votes>0.0 else 0.0

    def name_get(self):
        result = []
        for ast in self:
            name = '%s - (%s)' % (ast.name, ast.short_name)
            result.append((ast.id, name))
        return result
    # campos computados
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            args = args or []
            domain = [('state','=','new')]
            return self.search(expression.AND([domain, args]), limit=limit).name_get()
    
        return super(AssemblyMeeting, self).name_search(name=name, args=args, operator=operator, limit=limit)
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
    
    @api.depends('assembly_meet_type')
    def _compute_available_partner_ids(self):
        """
        Consigue todos los partner que posean al menos 1 accion.
        """
        for asm in self:
            if asm.state=='draft':
                partners = asm.env['res.partner'].search([])
                if asm.assembly_meet_type!='directory':
                    for am in asm:
                        am.partner_ids = partners.filtered(
                            lambda p: p.shares.ids != []
                            )
                elif asm.assembly_meet_type=='directory':
                    asm.env['res.partner'].search([])
                    for am in asm:
                        am.partner_ids=partners.search([('position.type','=',   'director')])
                else:
                    asm.partner_ids=[]
        
    date_start=fields.Datetime(string='Hora de Inicio', help='Hora de inicio de la reunion', required=True)
    date_end=fields.Datetime(string='Hora de Finalización', help='Hora de inicio de la reunion', required=True)
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
        ('extraordinary', 'Asamblea Extraordinaria'),
        ('directory','Directorio')
    ])
    description=fields.Text(string='Descripción', 
                            help='Rellene la descripción de la Reunión')
    
    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('progress','En Curso'),
        ('count','Conteo de Votos'),
        ('finished', 'Finalizada'),
        ('canceled', 'Cancelada')
    ], default='draft')

    partner_ids = fields.Many2many(string='Accionistas Presentes', 
                                   comodel_name='res.partner',
                                   column1='assembly_meeting', 
                                   column2='partner_id', 
                                   relation='assembly_meeting_partner', 
                                   compute='_compute_available_partner_ids',
                                   store=True)
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
                return UserWarning('No se puede establecer a borrador')

    def action_confirm(self):
        for meet in self:
           quorum_per_type={
                'ordinary': self.env.company.quorum_ord,
                'extraordinary': self.env.company.quorum_ext,
                'directory': self.env.company.quorum_ord,
           }
           is_quorum= self.quorum>= quorum_per_type[self.assembly_meet_type]
        if meet.state in ['draft'] and is_quorum:
                meet.state = 'new' 
                meet._create_event()
        else:
            return UserWarning('Ya ha sido confirmada previamente o no reune el quorum necesario')
    def action_start(self):
        """Comenzar reunion"""
        for meet in self:
            if meet.state in ['new']:
                meet.state = 'progress' 
                meet.date_start=fields.Datetime.now()
            # calculo y registro las asistencias
            for event in meet.event_id:
                for registration in event.registration_ids:
                    if registration.state=='open' : 
                        # si realmente confirmo la asistencia
                        if registration.partner_id.employee_ids:
                            reg_values={
                                "employee_id":registration.partner_id.employee_ids[0].id,
                                "check_in":meet.date_start,
                                "check_out":fields.datetime.now(),
                                "assembly_meeting": meet.id,
                            }
                        # partner=>empleado
                            self.env['hr.attendance'].create(reg_values)
                            registration.state='done'
                        # else: 
                        #     return UserWarning('Algunos asistentes no tienen la configuración \n correcta en el módulo de RR.HH')
            else:
                return UserWarning('No se puede finalizar la reunion')

    def action_start_count(self):
        """Comenzar Conteo de votos"""
        quorum_per_type={
                'ordinary': self.env.company.quorum_ord,
                'extraordinary': self.env.company.quorum_ext,
                'directory': self.env.company.quorum_ord,
           }
        is_quorum= self.quorum>= quorum_per_type[self.assembly_meet_type]
        for meet in self:
            if meet.state in ['progress'] and is_quorum:
                meet.state = 'count' 
            else:
                return UserWarning('La Reunión aún no esta en marcha')
            
    def action_finish(self):
        for meet in self:
            if meet.state in ['count']:
                meet.state = 'finished' 
                meet.date_end=fields.Datetime.now()
            else:
                return UserWarning('No se puede finalizar la reunion')
            
    def action_cancel(self):
        for meet in self:
           quorum_per_type={
                'ordinary': self.env.company.quorum_ord,
                'extraordinary': self.env.company.quorum_ext,
                'directory': self.env.company.quorum_ord,
           }
           is_quorum= self.quorum>= quorum_per_type[self.assembly_meet_type]
        if meet.state in ['draft','new'] or not is_quorum:
                meet.state = 'canceled' 
                for line in meet.assembly_meeting_line:
                    for topic in line.topic:
                        topic.action_set_canceled()
                        
    def action_check_partners(self):
        """Este helper comprueba la asistencia de accionsitas una vez que la reunion este en marcha"""
        for meet in self:
            if meet.state=='progress':
                update_partners=[]
                attendances=meet.env['hr.attendance'].search([('assembly_meeting','=',meet.id)])
                for hratt in attendances:
                    update_partners.append(hratt.employee_id.partner_id.id)

                meet.partner_ids=update_partners
            
    def _create_event(self):
        # Creamos los tickets
        event_vals=self._prepare_event_values()
        # Creamos el ticket
        ticket_vals=self._prepare_ticket_values()
        event_vals['event_ticket_ids'].append((0,0,ticket_vals))
        # Creamos una registración por cada partner
        for partner in self.partner_ids:
            reg_vals=self._prepare_reg_values()
            reg_vals.update({
                'name':'Accionista: %s' %(partner.name),
                'partner_id': partner.id,
                'email':partner.email,
                'mobile':partner.mobile,
                'phone':partner.phone,
                'state': 'draft',
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
            'state':'',
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

    def action_register_vote(self):
        ''' Open the account.payment.register wizard to pay the selected journal entries.
        :return: An action opening the account.payment.register wizard.
        '''
        return {
            'name': _('Registrar Voto'),
            'res_model': 'wizard.create.vote',
            'view_mode': 'form',
            'context': {
                'active_model': 'assembly.meeting',
                'active_ids': self.ids,
                'meeting':self.id,
                'type':'normal',
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }
    
class HrAttendance(models.Model):
    _inherit = "hr.attendance"
    assembly_meeting = fields.Many2one(
        string='Reunion Tratante', 
        comodel_name='assembly.meeting', 
        readonly=True)