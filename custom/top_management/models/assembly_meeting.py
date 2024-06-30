# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict
import logging
_logger = logging.getLogger(__name__)
from odoo.exceptions import UserError
from werkzeug import urls
import xml.etree.ElementTree as xee
from lxml import etree
from datetime import datetime, timedelta
from odoo import models, fields, api, tools
from odoo.exceptions import ValidationError
from odoo.osv import expression
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
    
    # Traversing methods
    @api.model
    def _get_partner_names(self):
        partner_ids=self.env['res.partner'].search([]).sorted(key='name', reversed=True)
        self.partner_text=' , '.join([partner.name] for partner in partner_ids) 

    # Compute methods
    @api.depends('partner_ids')
    def _compute_quorum(self):
        for ass in self:
            if ass.assembly_meet_type!='directory':
                shares=self.env['account.share'].search([])
                total_votes=sum([share.votes_num for share in shares])

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
    
    def print_assemblies(self):
        meetings=self.read_group(['|', '&', ('assembly_meet_type','=','ordinary'),
                                  ('assembly_meet_type','=','directory'),
                                  ('state','=','new')], ['company_id','duration:avg','name'],['quorum'],['name','date_start'], limit=10)
        print(meetings)
        
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
        
    date_assembly=fields.Datetime(string='Assembly Date', index=True, copy=False, default=fields.Datetime.now, help='Assembly Record Date')
    date_start=fields.Datetime(string='Hora de Inicio', help='Hora de inicio de la reunion', required=True)
    date_end=fields.Datetime(string='Hora de Finalización', help='Hora de inicio de la reunion', required=True)
    release_date=fields.Date(string='Revisión', groups='top_management.top_management_group_user_release')
    
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
    active = fields.Boolean(string='Activo: ', default=True)
    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('progress','En Curso'),
        ('count','Conteo de Votos'),
        ('finished', 'Finalizada'),
        ('canceled', 'Cancelada')
    ], default='draft')
    report_missing=fields.Text(string='Documentación', groups='top_management.top_management_group_manager')
    blocked=fields.Boolean(string='Bloqueado', default=False, required=True, help='Campo que establece la posibilidad de editarlo por parte de los usuarios comunes', groups='top_management.top_management_group_manager')

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
                         help='Porcentaje de Asistencia a la Reunión', store=True,
                         compute='_compute_quorum')
    
    user_id=fields.Many2one(string='Usuario', comodel_name='res.users', default=lambda self: self.env.user, readonly=True)


    partner_text=fields.Text(string='Texto de Prueba')

    # probando el metodo sudo (superusuario)

    def report_missing_assembly(self):
        self.ensure_one()
        message="El documento de la reunión se perdió (Reportado por: %s)"%self.env.user.name
        self.sudo(flag=True).write({
            'report_missing': message
        })

    def action_draft(self):
        for meet in self:
            if meet.state not in ['canceled', 'finished']:
                meet.state = 'draft'
            else:
                raise UserError('No se puede establecer a borrador')

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
            raise UserError('Ya ha sido confirmada previamente o no reune el quorum necesario')
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
                            #     raise UserError('Algunos asistentes no tienen la configuración \n correcta en el módulo de RR.HH')
            else:
                raise UserError('No se puede Comenzar la reunion')
            
    def load_default_lines(self):
        """ Esta funcion busca Asuntos de reunion no tratados y sin lineas y los carga automáticamente a la reunion"""
        for rec in self:
            available_topic_ids=rec.env['assembly.meeting.topic'].search([('meeting_assigned','=',False)]).filtered(lambda t:t.state=='new' and t.topic_meet=='assembly' and not t.assembly_meeting_line)
            topic_to_attach=[]
            if not self.env['assembly.meeting.line'].check_access_rights('create', False):
                try:
                    self.check_access_rights('write')
                    self.check_access_rule('write')
                except AccessError:
                    message_id = self.env['message.wizard'].create({'message': _("No Permitido")})
            for topic in available_topic_ids:
                topic_vals=dict([
                    ("name",'Asunto %s - %s'%(topic.short_name, topic.name)),
                    ("topic", topic.id),
                    ("priority",'normal'),
                    ('state','no_treating'),
                    ('assembly_meeting', rec.id),
                ])
                topic_to_attach.append(topic_vals)
                rec.env['assembly.meeting.line'].create(topic_to_attach)
            message_id = self.env['message.wizard'].create({'message': _("Se han cargado Lineas por Defecto: Aquellas que han sido adas de alta para tratamiento y para las que aun no hay reuniones asignadas. Por Favor Revise las correspondientes")})
        return {
                'name': _('Líneas Agregadas Exitosamente! 👍'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'message.wizard',
                # pass the id
                'res_id': message_id.id,
                'target': 'new'
                }

    def delete_lines(self):
        if not self.env['assembly.meeting.line'].check_access_rights('unlink', False):
            try:
                self.check_access_rights('write')
                self.check_access_rule('write')
            except AccessError:
                message_id = self.env['message.wizard'].create({'message': _("No Está autorizado a eliminar lineas!")})
        for rec in self:
            rec.assembly_meeting_line=[(5,)]
            
        message_id = self.env['message.wizard'].create({'message': _("Lineas Eliminadas Exitosamente!")})
        return {
                'name': _('Información: ! 👍'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'message.wizard',
                # pass the id
                'res_id': message_id.id,
                'target': 'new'
                }
    def action_test(self):
        for assembly in self:
            # Filtered
            # def predicate(vote):
            #     return vote.assembly_meeting==assembly and vote.type=='normal' and vote.result=='positive'
            
            # assembly_votes=assembly.env['assembly.meeting.vote'].search([]).filtered(predicate)

            # print('....Longitud', len(assembly_votes))
            # for vote in assembly_votes:
            #     print('..............', vote)
            #     print('..............', vote.type)

            # sorted
            
            partner_sorted=assembly.env['res.partner'].search([]).sorted(lambda p: p.name,reverse=True)
            for partner in partner_sorted:
                print('......', partner.name)
                print('........', partner_sorted[0]['name'])

            # mapped
            print('..... MAPPED.....')

            topic_ids=assembly.env['assembly.meeting.topic'].search([('num_votes_plus','<',500)]).sorted(key='short_name', reverse=True).mapped('id')

            print('topics:  ', topic_ids)
        
            # for t in topic_ids:
            #     print('---')
            #     print('... ',t)

            # assembly_vote_ids=assembly.env['assembly.meeting.vote'].search([]).mapped('short_name')
            # # acepta solo 1 argumento
            # for vote in assembly_vote_ids:
            #     print('..........', vote)
            # TODO !para buscar registros archivados!
            # para buscar registros archivados   
            #self.env['library.book'].with_context(active_test=False).search([])

            partner_ids=assembly.env['assembly.meeting.vote'].search([]).mapped('partner_id')
            for partner in partner_ids:
                print('............ partners ', partner.name)
            bank_ids=assembly.env['assembly.meeting.vote'].search([]).mapped('partner_id.bank_ids')
            for bank in bank_ids:
                print('............... banks', bank)

        # With context
            print('With context')
            product_category = self.env['product.category'].search([]).mapped('name')
            product_category_context = self.env['product.category'].with_context(lang='ar_SY').search([]).mapped('name')
            print("product_category...", product_category)
            print("product_category_context...", product_category_context)

        # SEARCH_READ()
            # self.search_read(domain=[],fields=[],offset=10,limit=10,order='short_name')
            topic_ids=assembly.env['assembly.meeting.topic'].search_read(domain=[('state','=','approved')], fields=['short_name','name','description','topic_type','num_votes_plus'],offset=2,limit=40, order='name')

            print('Topics (search_read): ', topic_ids)
            print('ID METHODS')

            print('external id: ', assembly.get_external_id())
            print('metadata: ', assembly.get_metadata())
        
            # Read_group()
            # self.read_group(domain=('active','=', True), fields=['name','short_name'],groupby=['assembly_meet_type'],limit=10,offset=1)
            print('....READGROUP')
            
            assembly_ids=assembly.env['assembly.meeting'].read_group(domain=[('active','=',True)], fields=['short_name','name','user_id'],groupby=['assembly_meet_type'],limit=10,offset=0)

            print('.....: aSSEMBLYES: ', assembly_ids)
            for assembly_group in assembly_ids:
                print('.....: %s'%(assembly_group))
            
            votes=assembly.env['assembly.meeting.vote'].read_group(domain=[], fields=['short_name','type','partner_id'],groupby=['partner_id'])
            print('Votes: ', votes)

            for vote in votes:
                print('vote: ', vote)

            topic_ids=assembly.env['assembly.meeting.topic'].search([]).read_group(domain=[], fields=['topic_type','num_votes_plus'], groupby=['topic_type'])
            print('Topics:-----: ', topic_ids)

            for topic in topic_ids:
                print('topic-----: ', topic)

            print('.....DISPLAY NAME.....')
            its_assembly=self.env['assembly.meeting.vote'].search([('id','=','5')])
            
            print('....: ', its_assembly.display_name)

            # # Read
            # dicts=assembly.env['assembly.meeting.vote'].search([]).read(['name','short_name','date','result','topic','partner_id'])
            # print('.................READ...................')
            # print(dicts)
            
            # for rec in dicts:
            #     print('dict: ',rec)

            print('.................REF...................')
            stage=assembly.env.ref('account_suscription_order.stage_new')
            print('Stage: ', stage.id)
            
            print('CREATE.......')
            vals={
                "name":'Creado desde create',
                "company_id": assembly.env.company.id,
                "gender":"male",
                "marital":"married",
                "certificate":"graduate"
            }
            created_record=assembly.env['hr.employee'].create(vals)
            print('...Created record: ', created_record, created_record.id)

            print('UPDATE.......')

            record_to_update=assembly.env['hr.employee'].browse(5)
            new_vals={
                "name":'Updated Vals',
                "company_id": assembly.env.company.id,
                "gender":"male",
                "marital":"married",
                "certificate":"graduate"
            }
            record_to_update.write(new_vals)

            print('------NEW-----------.')

            new_topic=assembly.env['assembly.meeting.topic'].new({
                "name":'Probando New:::',
                "description":'una nueva descripcion',
                "state":'new',
                "topic_type":"redemption",
            })
            print('new topic: ',new_topic)
            print('new topic: ',new_topic.name)
            
            print('::::::::::::::::::::::::::copy::::::--. ')

            record_copied=record_to_update.copy({
                'name':'copied values and name overrided',
            })

            print(record_copied)
            print('..............UNLINK...............')
            record_to_erase=assembly.env['assembly.meeting.topic'].browse(20).unlink()
            print('record to erase: ',record_to_erase)

            print('..............search_read.................')
            # self.search_read(domain=[], fields=[],offset=1, limit=100,order='name desc, date desc')

            print("------------SEARCH_READ--------------")

            votes=assembly.env['assembly.meeting.vote'].search_read(domain=[('type','=','normal')], fields=["name",'short_name','date','result','topic','partner_id'],offset=1, limit=100,order='name desc, date desc')

            for vote in votes:
                print(vote)
                print(vote['topic'])

            # FIELDS_GET
            # self.fields_get(allfields=[],attributes=[])
            purchase_ids=assembly.env['purchase.order'].fields_get(allfields=['name','priority','origin','date_order','state'],attributes=['readonly','default','help','selection','comodel_name','amount_total'])
            print('..........: ', purchase_ids)

            for purchaseField in purchase_ids:
                print(purchaseField)

            # UPDATE
            record_to_update=assembly.env['purchase.order'].browse(3).update({
                "notes":"New Description from update",
                "partner_id": assembly.env['res.partner'].browse(14).id
            })
            print(record_to_update)
    def action_start_count(self):
        """Comenzar Conteo de votos"""
        # Para iniciar el conteo, todos los accionistas presentes deben haber emitido su voto

        quorum_per_type={
                'ordinary': self.env.company.quorum_ord,
                'extraordinary': self.env.company.quorum_ext,
                'directory': self.env.company.quorum_ord,
           }
        is_quorum= self.quorum>= quorum_per_type[self.assembly_meet_type]
        for meet in self:
            if is_quorum:
                def predicate(vote):
                    return vote.assembly_meeting==meet and vote.type=='normal' and vote.topic==line.topic
                for partner in meet.partner_ids:
                    for line in meet.assembly_meeting_line:
                        # Filtered
                        partner_assembly_votes=meet.env['assembly.meeting.vote'].search([("partner_id",'=',partner.id)]).filtered(predicate)
                        if len(partner_assembly_votes)<1:
                            raise UserError(_('Alguno de los accionistas no ha votado'))
                        meet.state = 'count'
            else:
                raise UserError('La Reunión aún no esta en marcha')

    def action_finish(self):
        for meet in self:
            if meet.state in ['count']:
                for line in meet.assembly_meeting_line:
                    if line['state']=='no_treating': 
                        raise UserError(_('Error!. Los topicos deben aprobarse o rechazarse. No pueden quedar sin tratar'))
                meet.state = 'finished'
                meet.date_end=fields.Datetime.now()
            else:
                raise UserError('No se puede finalizar la reunion')
            
    def action_cancel(self):
        """Se cancela por falta de quorum sino se continua"""
        for meet in self:
           quorum_per_type={
                'ordinary': self.env.company.quorum_ord,
                'extraordinary': self.env.company.quorum_ext,
                'directory': self.env.company.quorum_ord,
           }
           is_quorum= self.quorum>= quorum_per_type[self.assembly_meet_type]
           if meet.blocked and not is_quorum:
               meet.with_context(write_desc=True)
        if meet.state in ['draft','new','progress'] or not is_quorum:
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
                meet._get_partner_names()
            
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
            seq_date = None
            if 'date_assembly' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date_assembly']))
                vals['short_name'] = self.env['ir.sequence'].next_by_code(
                    'assembly.meeting', sequence_date=seq_date) or _('New')
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
    def average_meeting_duration(self):
        self.flush()
        sql_query = """
            SELECT
            am.name,
            avg((EXTRACT(epoch from age(date_start, date_end)) / 86400))::int
            FROM
            assembly_meeting AS am
            WHERE am.state = 'finished'
            GROUP BY am.name;"""
        self.env.cr.execute(sql_query)
        result=self.env.cr.fetchone()()
        _logger.info("Duracion promedio de las reuniones: %s", result)
        result=self.env.cr.fetchall()
        _logger.info("Duracion promedio de las reuniones: %s", result)
        result=self.env.cr.dictfetchall()
        _logger.info("Duracion promedio de las reuniones: %s", result)

    def action_edit_xml(self):
        view_id = self.env.ref('assembly_meeting.assembly_meeting_view_form')
        view_arch = str(view_id.arch_base)
        doc = xee.fromstring(view_arch)
        field_list = []
        field_list_1 = []
        for tag in doc.findall('.//field'):
            field_list.append(tag.attrib['name'])


        model_id = self.env['ir.model'].sudo().search(
            [('model', '=', 'assembly.meeting')])
        
        return [('model_id', '=', model_id.id), ('state', '=', 'draft'),
        ('name', 'in', field_list)]


    def print_accounts(self):
        x = datetime(2024, 4, 1)
        assembly_votes=self.env['assembly.meeting.vote'].search_read(
            domain=['date','<',x.strftime('%Y-%m-%d')], 
            fields=['short_name','name','result','type'],
            order='date asc,short_name desc')

        for vote in assembly_votes:
            print(vote)

        print('PROBANDO JOURNAL')

    def get_SQL(self):
        for record in self:
            record._cr.execute(
                """SELECT assembly
                JOIN assembly_meeting_topic topic ON topic.assembly_meeting_line=assembly.id
                JOIN LEFT assembly_meeting_line aml ON aml.topic.id=assembly
                FROM assembly_meeting assembly
                WHERE assembly.state='finished'
                GROUP BY assembly.company_id                
                """, [tuple(self.ids)]
            )
            result=[row for row in record.env.cr.dictfetchall()]

            print(result)

class HrAttendance(models.Model):
    _inherit = "hr.attendance"
    assembly_meeting = fields.Many2one(
        string='Reunion Tratante', 
        comodel_name='assembly.meeting', 
        readonly=True)