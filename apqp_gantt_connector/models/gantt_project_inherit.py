# -*- coding: utf-8 -*-
from odoo import models, fields

class GanttProject(models.Model):
    _inherit = 'gantt.project'

    cft_team_ids = fields.Many2many('res.users', string='CFT Team')
    apqp_timeline_chart_id = fields.Many2one('apqp.timeline.chart', string='APQP Timeline Chart', ondelete='set null')
