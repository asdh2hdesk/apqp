# -*- coding: utf-8 -*-
from odoo import models, fields, api

class GanttMOM(models.Model):
    _inherit = 'gantt.mom'

    @api.onchange('project_id')
    def _onchange_project_id_cft(self):
        if self.project_id and hasattr(self.project_id, 'cft_team_ids'):
            self.cft_team_ids = [(6, 0, self.project_id.cft_team_ids.ids)]
        else:
            self.cft_team_ids = False

    @api.depends('project_id', 'project_id.cft_team_ids')
    def _compute_cft_team_ids(self):
        for mom in self:
            if mom.project_id and hasattr(mom.project_id, 'cft_team_ids'):
                mom.cft_team_ids = [(6, 0, mom.project_id.cft_team_ids.ids)]
            else:
                mom.cft_team_ids = False

    cft_team_ids = fields.Many2many(
        compute='_compute_cft_team_ids',
        store=True,
        readonly=False,
    )
