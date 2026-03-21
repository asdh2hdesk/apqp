# -*- coding: utf-8 -*-
from odoo import models, fields, api


class GanttStage(models.Model):
    _name = 'gantt.stage'
    _description = 'Gantt Task Stage'
    _order = 'sequence, id'

    name = fields.Char(
        string='Stage Name',
        required=True,
        translate=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    description = fields.Text(
        string='Description',
        translate=True,
    )
    fold = fields.Boolean(
        string='Folded in Kanban',
        default=False,
        help='If enabled, this stage will be folded in the kanban view.',
    )
    color = fields.Integer(
        string='Color Index',
        default=0,
    )
    task_ids = fields.One2many(
        comodel_name='gantt.task',
        inverse_name='stage_id',
        string='Tasks',
    )
    task_count = fields.Integer(
        string='Task Count',
        compute='_compute_task_count',
    )

    @api.depends('task_ids')
    def _compute_task_count(self):
        for stage in self:
            stage.task_count = len(stage.task_ids)

    def _get_default_stages(self):
        """Return default stages for new projects."""
        return [
            {'name': 'Draft', 'sequence': 1, 'color': 0},
            {'name': 'In Progress', 'sequence': 2, 'color': 2},
            {'name': 'Review', 'sequence': 3, 'color': 4},
            {'name': 'Done', 'sequence': 4, 'color': 10},
            {'name': 'Cancelled', 'sequence': 5, 'color': 1, 'fold': True},
        ]
