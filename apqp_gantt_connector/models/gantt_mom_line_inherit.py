# -*- coding: utf-8 -*-
from odoo import models, fields, api


class GanttMOMLineInherit(models.Model):
    _inherit = 'gantt.mom.line'

    def _check_auto_completion(self):
        """Extend to sync completion back to the linked APQP timeline format
        (Gate Review row), so its status/progress updates automatically."""
        res = super(GanttMOMLineInherit, self)._check_auto_completion()

        for record in self:
            if not record.task_id:
                continue

            apqp_format = self.env['apqp.timeline.format'].search([
                ('gantt_task_id', '=', record.task_id.id)
            ], limit=1)

            if not apqp_format:
                continue

            if record.status == 'done':
                if not apqp_format.actual_end_date:
                    apqp_format.with_context(skip_apqp_sync=True).write({
                        'actual_end_date': record.completion_date or fields.Date.context_today(record),
                    })
                    if not apqp_format.actual_start_date:
                        apqp_format.with_context(skip_apqp_sync=True).write({
                            'actual_start_date': apqp_format.actual_end_date,
                        })
            else:
                if apqp_format.actual_end_date:
                    apqp_format.with_context(skip_apqp_sync=True).write({
                        'actual_end_date': False,
                    })

        return res