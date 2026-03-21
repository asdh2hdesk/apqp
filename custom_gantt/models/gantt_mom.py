# -*- coding: utf-8 -*-
from odoo import models, fields, api


class GanttMOM(models.Model):
    _name = 'gantt.mom'
    _description = 'Minutes of Meeting'
    _order = 'project_id, id'
    _rec_name = 'subject'

    project_id = fields.Many2one(
        comodel_name='gantt.project',
        string='Project',
        required=True,
        ondelete='cascade',
        index=True,
    )
    subject = fields.Char(
        string='Meeting Subject',
        required=True,
        default='Minutes of Meeting',
    )
    # date = fields.Date(
    #     string='Meeting Date',
    #     required=True,
    #     default=fields.Date.today,
    # )
    # attendees = fields.Char(
    #     string='Attendees',
    #     help='Comma-separated list of attendees',
    # )
    line_ids = fields.One2many(
        comodel_name='gantt.mom.line',
        inverse_name='mom_id',
        string='MOM Points',
    )
    notes = fields.Html(
        string='Additional Notes',
    )
    champion_id = fields.Many2one(
        comodel_name='res.users',
        string='Champion',
        help='Person responsible for driving this MOM forward.',
    )
    cft_team_ids = fields.Many2many(
        comodel_name='res.users',
        relation='gantt_mom_cft_team_rel',
        column1='mom_id',
        column2='user_id',
        string='CFT Team',
        help='Cross-Functional Team members for this meeting.',
    )


class GanttMOMLine(models.Model):
    _name = 'gantt.mom.line'
    _description = 'Minutes of Meeting Line'
    _order = 'mom_id, sequence, id'

    mom_id = fields.Many2one(
        comodel_name='gantt.mom',
        string='MOM',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(
        string='Sr. No.',
        default=1,
    )
    points = fields.Text(
        string='Points Discussed',
        required=True,
    )
    date = fields.Date(
        string='Meeting Date',
        required=True,
        default=fields.Date.today,
    )
    responsible_id = fields.Many2one(
        comodel_name='res.users',
        string='Responsible',
        default=lambda self: self.env.user,
    )
    attendee_ids = fields.Many2many(
        comodel_name='hr.employee',
        relation='gantt_mom_line_employee_rel',
        column1='mom_line_id',
        column2='employee_id',
        string='Attendees',
    )
    remark = fields.Char(
        string='Remark',
    )
    target_date = fields.Date(
        string='Target Date',
    )
    completion_date = fields.Date(string='Actual Completion Date')
    status = fields.Selection(
        selection=[
            ('open', 'Open'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='open',
    )
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        relation='gantt_mom_line_attachment_rel',
        column1='mom_line_id',
        column2='attachment_id',
        string='Attachments',
    )
