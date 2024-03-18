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

class AssemblyMeetingTopicVoteStats(models.Model):
    _name = 'assembly.meeting.topic.vote.stats'
    _auto=False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        query = """
            CREATE OR REPLACE VIEW assembly_meeting_topic_vote_stats AS (
            SELECT

            count(am.id) as assembly_count,
            avg(num_votes_minus/)::int as average_occupation
            FROM
            assembly_meeting_topic AS amt
            JOIN
            assembly_meeting_line as aml ON aml.id IN amt.assembly_meeting_line
            JOIN 
            assembly_meeting as am ON am.id = aml.assembly_meeting
            WHERE amt.state = 'canceled'
            GROUP BY amt.assembly_meeting_line
            );
        """
        self.env.cr.execute(query)
        
    topic_id=fields.Many2one(string='Asunto', comodel_name='assembly.meeting.topic', help='Asunto de Reunión', readonly=True)
    assembly_count=fields.Integer(string='Reuniones que trataron', readonly=True)
    average_cancel=fields.Integer(string='Promedio Cancelaciones', readonly=True)