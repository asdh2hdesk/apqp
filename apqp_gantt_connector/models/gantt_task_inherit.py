# -*- coding: utf-8 -*-
from odoo import models, fields, api

class GanttTask(models.Model):
    _inherit = 'gantt.task'

    apqp_timeline_format_id = fields.Many2one('apqp.timeline.format', string='APQP Timeline Format',
                                              ondelete='set null')
    is_gate_review = fields.Boolean(string='Is Gate Review', default=False)
    gate_review_id = fields.Many2one('gate.review', string='Gate Review')

    def write(self, vals):
        """Override to sync changes back to APQP Timeline Format line."""
        res = super(GanttTask, self).write(vals)
        
        # Only sync if we're not already in a sync operation to avoid recursion
        if not self.env.context.get('skip_apqp_sync'):
            for task in self:
                if task.apqp_timeline_format_id:
                    sync_vals = {}
                    
                    # Planned dates sync
                    if 'date_start' in vals and task.date_start:
                        sync_vals['planned_start_date'] = task.date_start.date()
                    if 'date_stop' in vals and task.date_stop:
                        sync_vals['planned_end_date'] = task.date_stop.date()
                        
                    # Actual dates sync
                    if 'actual_date_start' in vals and task.actual_date_start:
                        sync_vals['actual_start_date'] = task.actual_date_start.date()
                    if 'actual_date_stop' in vals and task.actual_date_stop:
                        sync_vals['actual_end_date'] = task.actual_date_stop.date()
                        
                    # Progress sync: if 100%, set actual_end_date in APQP if not set
                    if 'progress' in vals and task.progress == 100.0 and not task.apqp_timeline_format_id.actual_end_date:
                        sync_vals['actual_end_date'] = fields.Date.today()
                    
                    if sync_vals:
                        task.apqp_timeline_format_id.with_context(skip_apqp_sync=True).write(sync_vals)
                        
        return res

    @api.model
    def archive_duplicate_phase_roots(self, project_id=None):
        """Archive legacy duplicate root (phase) tasks.

        Some projects accumulated two root tasks with the same name for a
        phase: an old placeholder created before APQP sync existed (no
        apqp_timeline_format_id, no attachments, always 0%), and the real
        one created/kept in sync by
        apqp.timeline.chart.action_create_sync_gantt() (linked via
        apqp_timeline_format_id, carries documents/attachments).

        This archives (active=False) the placeholder + its whole subtree
        whenever an APQP-linked sibling with the same name exists on the
        same project, so the Gantt view, list view, exports, and reports
        all stop showing the phase twice. Nothing is deleted, so it can be
        restored (Settings > Technical > Archived records) if needed.
        """
        domain = [('parent_id', '=', False)]
        if project_id:
            domain.append(('project_id', '=', project_id))
        roots = self.search(domain)

        groups = {}
        for r in roots:
            key = (r.project_id.id, r.name)
            groups[key] = groups.get(key, self.browse()) | r

        to_archive = self.browse()
        for (proj_id, name), group in groups.items():
            if len(group) > 1:
                linked = group.filtered('apqp_timeline_format_id')
                unlinked = group - linked
                # Only archive when we can clearly tell which copy is the
                # real one (i.e. at least one linked AND one unlinked).
                if linked and unlinked:
                    to_archive |= unlinked

        if to_archive:
            def _descendants(tasks):
                children = self.search([('parent_id', 'in', tasks.ids)])
                return children | _descendants(children) if children else children

            to_archive |= _descendants(to_archive)
            to_archive.write({'active': False})

        return to_archive