# -*- coding: utf-8 -*-
from odoo import models, fields, api


class GanttProject(models.Model):
    _name = 'gantt.project'
    _description = 'Gantt Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Project Name',
        required=True,
        tracking=True,
    )
    description = fields.Html(
        string='Description',
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Project Manager',
        default=lambda self: self.env.user,
        tracking=True,
    )
    date_start = fields.Date(
        string='Start Date',
        tracking=True,
    )
    date_end = fields.Date(
        string='End Date',
        tracking=True,
    )
    color = fields.Integer(
        string='Color Index',
        default=0,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    task_ids = fields.One2many(
        comodel_name='gantt.task',
        inverse_name='project_id',
        string='Tasks',
    )
    task_count = fields.Integer(
        string='Task Count',
        compute='_compute_task_count',
    )
    progress = fields.Float(
        string='Overall Progress',
        compute='_compute_progress',
        store=True,
        help='Computed from completed tasks / total tasks.',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer',
        tracking=True,
    )
    tag_ids = fields.Many2many(
        comodel_name='gantt.tag',
        string='Tags',
    )
    mom_ids = fields.One2many(
        comodel_name='gantt.mom',
        inverse_name='project_id',
        string='Minutes of Meeting',
    )
    mom_count = fields.Integer(
        string='MOM Count',
        compute='_compute_mom_count',
    )

    @api.depends('mom_ids')
    def _compute_mom_count(self):
        for project in self:
            project.mom_count = len(project.mom_ids)

    @api.depends('task_ids')
    def _compute_task_count(self):
        for project in self:
            project.task_count = len(project.task_ids)

    @api.depends('task_ids.progress', 'task_ids')
    def _compute_progress(self):
        for project in self:
            tasks = project.task_ids
            if tasks:
                project.progress = sum(tasks.mapped('progress')) / len(tasks)
            else:
                project.progress = 0.0

    def action_open_mom(self):
        """Find or create the single MOM for this project and open it directly."""
        mom = self.env['gantt.mom'].sudo().search(
            [('project_id', '=', self.id)], limit=1
        )
        if not mom:
            mom = self.env['gantt.mom'].sudo().create({
                'project_id': self.id,
                'subject': 'MOM — %s' % self.name,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': 'MOM — %s' % self.name,
            'res_model': 'gantt.mom',
            'res_id': mom.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }

    def action_open_gantt(self):
        """Open the Gantt Chart client action filtered to this project."""
        return {
            'type': 'ir.actions.client',
            'tag': 'custom_gantt.GanttChartAction',
            'name': '%s – Gantt' % self.name,
            'context': {
                'default_project_id': self.id,
                'gantt_project_id': self.id,
                'gantt_project_name': self.name,
            },
        }