from odoo import models, fields, api, _, exceptions
from odoo.exceptions import UserError


class APQPTimelineFormat(models.Model):
    _inherit = 'apqp.timeline.format'

    gantt_task_id = fields.Many2one('gantt.task', string='Gantt Task', ondelete='set null')

    def write(self, vals):
        """Override to sync changes back to the linked Gantt task."""
        res = super(APQPTimelineFormat, self).write(vals)

        # Only sync if we're not already in a sync operation
        if not self.env.context.get('skip_apqp_sync'):
            for line in self:
                if line.gantt_task_id:
                    sync_vals = {}

                    from datetime import datetime, time
                    def to_dt(d, t=time.min):
                        if not d: return False
                        return datetime.combine(d, t)

                    if 'name' in vals:
                        sync_vals['name'] = line.name
                    if 'planned_start_date' in vals:
                        sync_vals['date_start'] = to_dt(line.planned_start_date, time.min)
                    if 'planned_end_date' in vals:
                        sync_vals['date_stop'] = to_dt(line.planned_end_date, time.max)
                    if 'actual_start_date' in vals:
                        sync_vals['actual_date_start'] = to_dt(line.actual_start_date, time.min)
                    if 'actual_end_date' in vals:
                        sync_vals['actual_date_stop'] = to_dt(line.actual_end_date, time.max)
                    if 'status' in vals and line.status == 'completed':
                        sync_vals['progress'] = 100.0

                    if sync_vals:
                        line.gantt_task_id.with_context(skip_apqp_sync=True).write(sync_vals)
        return res

    def action_open_phase_mom(self):
        self.ensure_one()
        if not self.gantt_task_id:
            # Try to sync first
            self.timeline_chart_id.action_create_sync_gantt()

        if not self.gantt_task_id:
            raise UserError(_("No Gantt task linked to this phase. Please click 'Sync/Add Gantt' first."))

        project = self.timeline_chart_id.gantt_project_id
        if not project:
            raise UserError(_("No Gantt project linked to this chart."))

        # Find or create MOM for the project
        mom = self.env['gantt.mom'].search([('project_id', '=', project.id)], limit=1)
        if not mom:
            mom = self.env['gantt.mom'].create({
                'project_id': project.id,
                'subject': f"{project.name} - Phase MOM",
            })

        # Find or create MOM line for this task
        mom_line = self.env['gantt.mom.line'].search([
            ('mom_id', '=', mom.id),
            ('task_id', '=', self.gantt_task_id.id)
        ], limit=1)

        if not mom_line:
            mom_line = self.env['gantt.mom.line'].create({
                'mom_id': mom.id,
                'task_id': self.gantt_task_id.id,
                'agenda': self.name,
            })

        # Auto-fetch Gate Review points if it's a gate review
        if self.is_gate_review and self.gate_review_id:
            for point in self.gate_review_id.point_ids:
                existing_point = self.env['gantt.mom.discussion_point'].search([
                    ('mom_line_id', '=', mom_line.id),
                    ('name', '=', point.point_id.name)
                ], limit=1)

                if not existing_point:
                    self.env['gantt.mom.discussion_point'].create({
                        'mom_line_id': mom_line.id,
                        'name': point.point_id.name,
                    })

        return {
            'type': 'ir.actions.act_window',
            'name': _('MOM for %s') % self.name,
            'res_model': 'gantt.mom.line',
            'res_id': mom_line.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {'create': False},
        }

    def action_show_phase_remarks(self):
        self.ensure_one()
        if not self.gantt_task_id:
            raise UserError(_("No Gantt task linked to this phase."))

        mom_line = self.env['gantt.mom.line'].search([
            ('task_id', '=', self.gantt_task_id.id)
        ], limit=1)

        if not mom_line:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No MOM found'),
                    'message': _('No Minutes of Meeting found for this phase.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Discussion Points: %s') % self.name,
            'res_model': 'gantt.mom.discussion_point',
            'view_mode': 'list',
            'views': [[False, 'list']],
            'domain': [('mom_line_id', '=', mom_line.id)],
            'target': 'new',
        }