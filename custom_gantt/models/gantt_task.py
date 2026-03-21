# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class GanttTag(models.Model):
    _name = 'gantt.tag'
    _description = 'Gantt Task Tag'

    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer(string='Color Index', default=0)


class GanttTask(models.Model):
    _name = 'gantt.task'
    _description = 'Gantt Chart Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start, priority desc, id'
    _rec_name = 'name'

    # ─── Core Fields ────────────────────────────────────────────────────────────

    name = fields.Char(
        string='Task Name',
        required=True,
        tracking=True,
    )
    description = fields.Html(
        string='Description',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
    )
    sequence_handle = fields.Integer(string="Sequence no", default=1)

    # ─── People ─────────────────────────────────────────────────────────────────

    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Assigned To',
        default=lambda self: self.env.user,
        tracking=True,
        index=True,
    )
    reviewer_id = fields.Many2one(
        comodel_name='res.users',
        string='Reviewer',
        tracking=True,
    )

    # ─── Project & Stage ────────────────────────────────────────────────────────

    project_id = fields.Many2one(
        comodel_name='gantt.project',
        string='Project',
        ondelete='cascade',
        tracking=True,
        index=True,
    )
    stage_id = fields.Many2one(
        comodel_name='gantt.stage',
        string='Stage',
        ondelete='restrict',
        tracking=True,
        group_expand='_read_group_stage_ids',
        index=True,
        default=lambda self: self.env['gantt.stage'].search([], order='sequence', limit=1),
    )
    tag_ids = fields.Many2many(
        comodel_name='gantt.tag',
        string='Tags',
    )

    # ─── Sub-tasks ──────────────────────────────────────────────────────────────

    parent_id = fields.Many2one(
        comodel_name='gantt.task',
        string='Parent Task',
        ondelete='cascade',
        index=True,
        domain="[('project_id', '=', project_id), ('id', '!=', id)]",
    )
    child_ids = fields.One2many(
        comodel_name='gantt.task',
        inverse_name='parent_id',
        string='Sub-tasks',
    )
    subtask_count = fields.Integer(
        string='Sub-tasks',
        compute='_compute_subtask_count',
    )

    serial_no = fields.Char(
        string='No.',
        compute='_compute_serial_no',
        store=False,
        help='Hierarchical serial number e.g. 1, 2, 1.1, 1.2',
    )

    @api.depends('child_ids')
    def _compute_subtask_count(self):
        for task in self:
            task.subtask_count = len(task.child_ids)

    def _compute_serial_no(self):
        """
        Assign hierarchical serial numbers per project:
          Root tasks  → 1, 2, 3 ...
          Sub-tasks   → 1.1, 1.2, 2.1 ...
        """
        # Group tasks by project
        projects = {}
        for task in self:
            key = task.project_id.id or 0
            projects.setdefault(key, []).append(task)

        for project_id, tasks in projects.items():
            # Fetch ALL tasks in this project ordered by id to get stable numbering
            all_tasks = self.search(
                [('project_id', '=', project_id)] if project_id else [('project_id', '=', False)],
                order='id asc'
            )
            # Build number map
            number_map = {}
            root_counter = 0
            child_counters = {}

            for t in all_tasks:
                if not t.parent_id:
                    root_counter += 1
                    number_map[t.id] = str(root_counter)
                    child_counters[t.id] = 0
                else:
                    parent_id = t.parent_id.id
                    # Make sure parent is numbered (may not be in current batch)
                    if parent_id not in number_map:
                        # Find parent's number recursively
                        parent_num = number_map.get(parent_id, '')
                        if not parent_num:
                            number_map[parent_id] = '?'
                    child_counters.setdefault(parent_id, 0)
                    child_counters[parent_id] += 1
                    parent_num = number_map.get(parent_id, '?')
                    number_map[t.id] = '%s.%d' % (parent_num, child_counters[parent_id])

            # Assign to tasks in current recordset
            for task in tasks:
                task.serial_no = number_map.get(task.id, '')

    # ─── Dates ──────────────────────────────────────────────────────────────────

    # Planned dates (used by Gantt bars)
    date_start = fields.Datetime(
        string='Planned Start',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
    )
    date_stop = fields.Datetime(
        string='Planned End',
        required=True,
        default=lambda self: fields.Datetime.now() + timedelta(days=1),
        tracking=True,
    )
    duration = fields.Float(
        string='Planned Duration (days)',
        compute='_compute_duration',
        store=True,
    )

    # Actual dates
    actual_date_start = fields.Datetime(
        string='Actual Start',
        tracking=True,
        help='The actual date this task was started.',
    )
    actual_date_stop = fields.Datetime(
        string='Actual End',
        tracking=True,
        help='The actual date this task was completed.',
    )
    actual_duration = fields.Float(
        string='Actual Duration (days)',
        compute='_compute_actual_duration',
        store=True,
    )

    # ─── Priority & Progress ────────────────────────────────────────────────────

    priority = fields.Selection(
        selection=[
            ('0', 'Normal'),
            ('1', 'Important'),
            ('2', 'Very Urgent'),
            ('3', 'Critical'),
        ],
        string='Priority',
        default='0',
        tracking=True,
    )
    remark = fields.Char(
        string='Remark',
        tracking=True,
    )
    progress = fields.Float(
        string='Progress (%)',
        compute='_compute_progress',
        store=True,
        readonly=False,
        recursive=True,
        tracking=True,
        help='Task completion percentage (0–100). Auto-computed from sub-tasks if any exist.',
    )

    @api.depends('child_ids.progress', 'child_ids')
    def _compute_progress(self):
        for task in self:
            if task.child_ids:
                # Auto-compute from sub-tasks average
                task.progress = sum(task.child_ids.mapped('progress')) / len(task.child_ids)
            # If no sub-tasks, keep existing manual value (readonly=False allows editing)
    color = fields.Integer(
        string='Color Index',
        compute='_compute_color',
        store=True,
        help='Derived from stage color for Gantt bar coloring.',
    )

    # ─── Dependencies ───────────────────────────────────────────────────────────

    depend_on_ids = fields.Many2many(
        comodel_name='gantt.task',
        relation='gantt_task_dependency_rel',
        column1='task_id',
        column2='depends_on_id',
        string='Depends On',
        help='Tasks that must be completed before this one can start.',
    )
    dependent_ids = fields.Many2many(
        comodel_name='gantt.task',
        relation='gantt_task_dependency_rel',
        column1='depends_on_id',
        column2='task_id',
        string='Blocks',
    )

    # ─── Milestone ──────────────────────────────────────────────────────────────

    is_milestone = fields.Boolean(
        string='Is Milestone',
        default=False,
        help='Mark this task as a milestone (a key project checkpoint).',
    )

    # ─── Computed ───────────────────────────────────────────────────────────────

    @api.depends('actual_date_start', 'actual_date_stop')
    def _compute_actual_duration(self):
        for task in self:
            if task.actual_date_start and task.actual_date_stop:
                delta = task.actual_date_stop - task.actual_date_start
                task.actual_duration = delta.total_seconds() / 86400.0
            else:
                task.actual_duration = 0.0

    @api.depends('date_start', 'date_stop')
    def _compute_duration(self):
        for task in self:
            if task.date_start and task.date_stop:
                delta = task.date_stop - task.date_start
                task.duration = delta.total_seconds() / 86400.0
            else:
                task.duration = 0.0

    @api.depends('stage_id', 'stage_id.color')
    def _compute_color(self):
        for task in self:
            task.color = task.stage_id.color if task.stage_id else 0

    # ─── Constraints ────────────────────────────────────────────────────────────

    @api.constrains('actual_date_start', 'actual_date_stop')
    def _check_actual_dates(self):
        for task in self:
            if task.actual_date_start and task.actual_date_stop:
                if task.actual_date_stop < task.actual_date_start:
                    raise ValidationError(
                        _('Actual end date cannot be earlier than actual start date.')
                    )

    @api.constrains('date_start', 'date_stop')
    def _check_dates(self):
        for task in self:
            if task.date_start and task.date_stop:
                if task.date_stop < task.date_start:
                    raise ValidationError(
                        _('The end date (%s) cannot be earlier than the start date (%s).',
                          task.date_stop, task.date_start)
                    )

    @api.constrains('progress')
    def _check_progress(self):
        for task in self:
            if not (0.0 <= task.progress <= 100.0):
                raise ValidationError(_('Progress must be between 0 and 100.'))

    # ─── Group Expand ───────────────────────────────────────────────────────────

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """Always show all stages in grouped views."""
        return stages.search([], order=order)

    # ─── Onchange ───────────────────────────────────────────────────────────────

    @api.onchange('is_milestone')
    def _onchange_is_milestone(self):
        """Set end date equal to start date for milestones."""
        if self.is_milestone and self.date_start:
            self.date_stop = self.date_start

    @api.onchange('stage_id')
    def _onchange_stage_id(self):
        """Auto-set progress to 100% when task reaches the last stage."""
        if self.stage_id:
            last_stage = self.env['gantt.stage'].search(
                [], order='sequence desc', limit=1
            )
            if self.stage_id == last_stage:
                self.progress = 100.0

    # ─── Utility ────────────────────────────────────────────────────────────────

    def action_open_subtasks(self):
        """Open sub-tasks list for this task."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sub-tasks of %s' % self.name,
            'res_model': 'gantt.task',
            'view_mode': 'list,form',
            'domain': [('parent_id', '=', self.id)],
            'context': {
                'default_parent_id': self.id,
                'default_project_id': self.project_id.id,
            },
        }

    def action_mark_done(self):
        """Mark the task as done (progress = 100)."""
        self.write({'progress': 100.0})
        done_stage = self.env['gantt.stage'].search(
            [('name', 'ilike', 'done')], limit=1
        )
        if done_stage:
            self.write({'stage_id': done_stage.id})

    def action_reset_to_draft(self):
        """Reset the task back to the first stage."""
        draft_stage = self.env['gantt.stage'].search([], order='sequence', limit=1)
        if draft_stage:
            self.write({'stage_id': draft_stage.id, 'progress': 0.0})