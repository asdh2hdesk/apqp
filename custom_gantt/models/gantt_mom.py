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
    project_name = fields.Char(related='project_id.name', string='Project Name', readonly=True)
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

    @api.model
    def default_get(self, fields_list):
        defaults = super(GanttMOM, self).default_get(fields_list)
        if 'champion_id' in fields_list and not defaults.get('champion_id'):
            defaults['champion_id'] = self.env.user.id
        return defaults


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
    agenda = fields.Char(string='Agenda')
    points = fields.Text(
        string='Points Discussed',
    )
    date = fields.Date(
        string='Meeting Date',
        required=True,
        default=fields.Date.today,
    )
    start_date = fields.Date(string='Start Date', readonly=True)
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
    task_id = fields.Many2one(
        comodel_name='gantt.task',
        string='Linked Task',
        help='The Gantt Task associated with this MOM point.',
    )
    discussion_point_ids = fields.One2many(
        comodel_name='gantt.mom.discussion_point',
        inverse_name='mom_line_id',
        string='Discussion Points',
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

    def action_start(self):
        """Action to start the MOM line point tracking."""
        for record in self:
            if not record.start_date:
                record.start_date = fields.Date.context_today(record)
            if record.status == 'open':
                record.status = 'in_progress'
        return True

    def _check_auto_completion(self):
        """Check if all discussion points are closed and update completion status."""
        for record in self:
            if record.discussion_point_ids and all(p.status == 'closed' for p in record.discussion_point_ids):
                if not record.completion_date:
                    record.completion_date = fields.Date.context_today(record)
                record.status = 'done'
            elif record.status == 'done':
                # If some points are reopened, maybe reset status to in_progress?
                # record.status = 'in_progress'
                pass


class GanttMOMDiscussionPoint(models.Model):
    _name = 'gantt.mom.discussion_point'
    _description = 'MOM Discussion Point'
    _order = 'mom_line_id, sequence, id'

    mom_line_id = fields.Many2one(
        comodel_name='gantt.mom.line',
        string='MOM Line',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    serial_no = fields.Char(
        string='Sr. No.',
        compute='_compute_serial_no',
    )
    name = fields.Text(
        string='Points',
        required=True,
    )
    raised_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Points Raised By',
        default=lambda self: self.env.user,
    )
    status = fields.Selection(
        selection=[
            ('open', 'Open'),
            ('in_process', 'In Process'),
            ('closed', 'Closed'),
        ],
        string='Status',
        default='open',
    )
    responsibility_id = fields.Many2one(
        comodel_name='res.users',
        string='Responsibility',
    )

    target_date = fields.Date(
        string="Target Date",
        tracking=True
    )

    actual_completion_date = fields.Date(
        string="Actual Completion Date",
        tracking=True
    )

    attachment = fields.Binary(
        string="Attachment",
        attachment = True,
    )

    attachment_filename = fields.Char(
        string="File Name",
        store=True,
    )

    # Related fields for consolidated view
    project_id = fields.Many2one(
        comodel_name='gantt.project',
        string='Project',
        related='mom_line_id.mom_id.project_id',
        store=True,
        readonly=True,
    )
    project_name = fields.Char(
        string='Project Name',
        related='mom_line_id.mom_id.project_id.name',
        store=True,
        readonly=True,
    )
    agenda = fields.Char(
        string='Agenda',
        related='mom_line_id.agenda',
        store=True,
        readonly=True,
    )
    meeting_date = fields.Date(
        string='Meeting Date',
        related='mom_line_id.date',
        store=True,
        readonly=True,
    )

    @api.onchange('status')
    def _onchange_status(self):
        for rec in self:
            if rec.status == 'closed':
                rec.actual_completion_date = fields.Date.today()
            else:
                rec.actual_completion_date = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('status') == 'closed':
                vals['actual_completion_date'] = fields.Date.today()
        records = super().create(vals_list)
        for record in records:
            record.mom_line_id._check_auto_completion()
        return records

    def write(self, vals):
        if vals.get('status') == 'closed':
            vals['actual_completion_date'] = fields.Date.today()
        res = super().write(vals)
        if 'status' in vals:
            for record in self:
                record.mom_line_id._check_auto_completion()
        return res

    @api.depends('mom_line_id.discussion_point_ids', 'sequence')
    def _compute_serial_no(self):
        """Compute the serial number based on the sequence in the line."""
        for line in self.mapped('mom_line_id'):
            # Sort discussion points by sequence and id
            points = line.discussion_point_ids.sorted(key=lambda p: (p.sequence, p._origin.id or 0))
            for index, point in enumerate(points):
                point.serial_no = str(index + 1)
