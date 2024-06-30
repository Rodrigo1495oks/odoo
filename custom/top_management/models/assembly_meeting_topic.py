# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, timedelta
from odoo import models, fields, api, tools
from odoo.exceptions import ValidationError
from odoo.addons.base.models.res_partner import _tz_get
from odoo.osv import expression
from odoo.tools.translate import _
from odoo.tools.misc import get_lang
from odoo.tools import pycompat
from odoo.exceptions import UserError, AccessError

assemblyTopics=[
        'balance',
        'income', 
        'distribution',
        'memory', 
        'receiver', 
        'responsabilities', 
        'issuance',
        'issuance_1', 
        'redemption', 
        'amort', 
        'fusion', 
        'trans', 
        'dis',
        'susp',
        'deb',
        'conv',
        'certificates',
        'reduction',
        'irrevocable',
        'share_sale',
]

directoryTopics=[
        'power',
        'furniture',
        'contracts',
        'personal',
        'power_acts',
        'debts',
        'dependencies',
        'hiring',
        'procedure', 
        'finance', 
]
class AssemblyMeetingTopic(models.Model):
    _name = 'assembly.meeting.topic'
    # _inherits = {'account.asset', 'ref_name'}
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Objeto Temas de reunion'
    _order = 'short_name desc, name desc'
    _rec_name = 'short_name'

    # campos computados
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            args = args or []
            domain = [('state','=','new'), ('meeting_assigned','=',True)]
            return self.search(expression.AND([domain, args]), limit=limit).name_get()
    
        return super(AssemblyMeetingTopic, self).name_search(name=name, args=args, operator=operator, limit=limit)

    @api.depends('assembly_meeting_line')
    def _compute_meeting_assigned(self):
        for record in self:
            if len(record.assembly_meeting_line)>0:
                record.meeting_assigned = True
            else:
                record.meeting_assigned = False

    @api.depends('topic_type')
    def _compute_meet_type(self):
        for rec in self:
            if rec.topic_type in assemblyTopics:
                rec.topic_meet='assembly'
            elif rec.topic_type in directoryTopics:
                rec.topic_meet='directory'
        
    @api.depends('assembly_vote')
    def _compute_num_votes(self):
        votes_plus=0
        votes_minus=0
        votes_blank=0
        for topic in self:
            for vote in topic.assembly_vote:
                if vote.result=='positive':
                    votes_plus+=1
                elif vote.result=='negative':
                    votes_minus+=1
                else:
                    votes_blank+=1
            topic.num_votes_plus=votes_plus
            topic.num_votes_minus=votes_minus
            topic.num_votes_blank=votes_blank

    active = fields.Boolean(string='Active', default=True)
    
    short_name = fields.Char(
        string='Referencia', required=True, index='trigram', copy=False, default='New')
    name = fields.Char(string='Título')
    description = fields.Text(
        string='Descripción del tema a tratar', ondelete='restrict')
    meeting_assigned = fields.Boolean(
        string='Reunión Asignada', default=False, readonly=True, compute='_compute_meeting_assigned')
    state = fields.Selection(string='Estado', selection=[
        ('draft', 'Borrador'),
        ('new', 'Nuevo'),
        ('approved', 'Aprobado'),
        ('refused', 'Rechazado'),
        ('canceled', 'Cancelado')
    ], default='draft', required=True, readonly=True)
    topic_meet=fields.Selection(string='Tipo de Reunión', 
                                selection=[('directory','Directorio'),('assembly','Asambleas')], 
                                default='directory', compute='_compute_meet_type')
    topic_type = fields.Selection(string='Tipo de Asunto', selection=[
        # Topicos de Asamblea
        ('balance', 'Balance General'),
        ('income', 'Estado de Resultados'),
        ('distribution', 'Distribucion de Dividendos'),
        ('memory', 'Memoria'),
        ('receiver', 'Informe del Síndico'),
        ('responsabilities', 'Responsabilidades'),
        ('issuance', 'Emisión de Acciones'),
        ('issuance_1', 'Emisión de Acciones art 235'),
        ('redemption', 'Rescate de Acciones en Cartera y Reembolso'),
        ('amort', 'Amortización de Acciones'),
        ('fusion', 'Fusión'),
        ('trans', 'Transformación'),
        ('dis', 'Disolución'),
        ('susp','Limitacion o suspensión en el Derecho de Preferencia'),
        ('deb','Emisión de Debentures'),
        ('conv','Conversión en acciones'),
        ('certificates','Emisión de Bonos'),
        ('reduction', 'Reducción y Reintegro del Capital'),
        ('irrevocable', 'Aporte Irrevocable'),
        ('share_sale', 'Venta de Acciones'),
        # Topicos de Directorio (Estatuto)
        ('power', 'Otorgar Poderes Generales o Especiales'),
        ('furniture', 'Operaciones con Muebles e Inmuebles'),
        ('contracts', 'Autorización de Contratos'),
        ('personal', 'Autorización Dotación del Personal'),
        ('power_acts', 'Autorizacion Actos que Requieren poder Judicial'),
        ('debts', 'Autorización Operaciones Financieras (Préstamos, Bancos)'),
        ('dependencies', 'Autorización - Administración Dependencias, Sedes, Sectores y Departamentos, Segmentos, Regiones'),
        ('hiring', 'Aprobación Regimen de Contrataciones'),
        ('procedure', 'Reglamento Interno (Normas y Manuales de Procedimiento)'),
        ('finance', 'Planificacion Economico - Financiera'),

    ],store=True ,required=True, help='Asuntos correspondientes a asambleas ordinarias y extraordinarias, fijados por el Articulo 234 y 235 de la LGS')
    num_votes_plus=fields.Integer(string='Votos Positivos', 
                             help='Número de votos que este tópico ha recibido', 
                             compute='_compute_num_votes', 
                             default=0.0)
    num_votes_minus=fields.Integer(string='Votos Negativos', 
                             help='Número de votos que este tópico ha recibido', 
                             compute='_compute_num_votes', 
                             default=0.0)
    num_votes_blank=fields.Integer(string='Votos Neutros', 
                             help='Número de votos que este tópico ha recibido', 
                             compute='_compute_num_votes', 
                             default=0.0)
    # secuencia numerica
    # emision de acciones
    share_issuance=fields.One2many(string='Emisión de Acciónes', comodel_name='account.share.issuance', readonly=False, inverse_name='topic')

    # onchanges
    # @api.onchange("topic_meet")
    # def _onchange_all_partner_ids(self):
    #     res = {}
    #     res['domain'] = {'partner_id': [('id', '=',   ['1','2','3','4','5'] )], } 
    #     return res
    def action_confirm(self):
        for topic in self:
            if topic.state not in ['new']:
                topic.state = 'new'
            else:
                raise UserError('topico ya tratado o reunion no establecida')

    def name_get(self):
        result = []
        for topic in self:
            share_issuances = topic.share_issuance.mapped('short_name')
            name = '%s (%s)-(%s)' % (topic.short_name, ', '.join(share_issuances),topic.name)
            result.append((topic.id, name))
        return result

    def _action_approve_topic(self):
        for topic in self:
            """Para aprobar el topico necesito computar las mayorias"""
            if topic.state == 'new':
                topic.state = 'approved'
            else:
                raise UserError('No puede aprobarse este tópico')

    def _action_refuse_topic(self):
        for topic in self:
            if topic.state not in ['draft', 'approved', 'refused','canceled']:
                topic.state = 'refused'
            else:
                raise UserError('No puede rechazarse este tópico')

    def action_draft(self):
        """Solo cuando un asunto es cancelado, al ser cancelada la reunion
            puede ponerse en borrador a solicitud del interesado
        """
        for meet in self:
            if meet.state in ['new','canceled']:
                meet.state = 'draft'

    def action_set_canceled(self):
        for topic in self:
            if topic.state in ['new']:
                topic.state = 'canceled'
                if topic._context.get('write_desc'):
                    topic.write({
                        'description': 'La Reunión de este topico se cancelo'
                    })
            else:
                raise UserError(
                    'No puede Cancelarse un tópico que ya esta cancelado o aprobado')
    
    def action_archive(self):
        for rec in self:
            if any([not self.user_has_groups('top_management.top_management_group_manager'), self.state in ['draft','cancel']]):
                raise AccessError(_('No puede archivar Temas de Reunión'))
        return super().action_archive()
    
    @api.model
    def create(self, vals):
        if vals.get('short_name', _('New')) == _('New'):
                vals['short_name'] = self.env['ir.sequence'].next_by_code(
                    'assembly.meeting.topic') or _('New')
        return super().create(vals)
    
    @api.ondelete(at_uninstall=False)
    def _unlink_if_cancelled(self):
        for order in self:
            if order.state in ['new','approved','refused'] and order.active:
                raise UserError(_('In order to delete a Topic, you must cancel it first.'))