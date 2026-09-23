# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DocumentPackageInherit(models.Model):
    _inherit = 'xf.doc.approval.document.package'

    apqp_timeline_chart_id = fields.Many2one('apqp.timeline.chart', string='APQP Timeline Chart', readonly=True, copy=False)
    phase_timeframe_ids = fields.One2many('apqp.project.phase.timeframe', 'document_package_id', string='Phase Timeframes')

    @api.onchange('phase_timeframe_ids', 'start_date')
    def _onchange_phase_timeframes(self):
        """Update target_date and phase planned dates when timeframes change."""
        self._compute_apqp_target_date()

    def _add_working_days(self, start_date, days):
        """Add days while skipping Sundays."""
        from datetime import timedelta
        current_date = start_date
        added_days = 0
        while added_days < days:
            current_date += timedelta(days=1)
            # 6 is Sunday in weekday() where Monday is 0
            if current_date.weekday() != 6:
                added_days += 1
        return current_date

    def _compute_apqp_target_date(self):
        """Internal method to calculate dates and update target_date."""
        for record in self:
            if not record.start_date:
                continue
            
            current_start = record.start_date
            last_end = current_start
            
            # Sort timeframes by phase sequence
            timeframes = record.phase_timeframe_ids.sorted('sequence')
            
            for tf in timeframes:
                tf.planned_start_date = current_start
                
                duration = tf.duration_value
                if tf.duration_unit == 'weeks':
                    duration *= 7
                    
                current_end = record._add_working_days(current_start, duration)
                tf.planned_end_date = current_end
                
                # Next phase starts when this one ends
                current_start = current_end
                last_end = current_end
            
            # Update project target date based on last phase end date
            if timeframes:
                record.target_date = last_end

    def action_update_phase_dates(self):
        """Update planned dates for all documents based on phase timeframes."""
        from datetime import timedelta
        self.ensure_one()
        self._compute_apqp_target_date()
        
        for tf in self.phase_timeframe_ids:
            # Update all document approvals in this phase
            approvals = self.document_approval_ids.filtered(lambda x: x.phase_id == tf.phase_id)
            if approvals:
                # Omit plan_start_date and plan_end_date update if they shouldn't be changed here?
                # User says: "plan start date and plan end date shoulld eb auto matically generated based on the time frame"
                approvals.write({
                    'plan_start_date': tf.planned_start_date,
                    'plan_end_date': tf.planned_end_date,
                })
            
            # Update additional attachments in this phase
            if self.apqp_timeline_chart_id:
                attachments = self.apqp_timeline_chart_id.attachment_ids.filtered(lambda x: x.phase_id == tf.phase_id)
                if attachments:
                    attachments.write({
                        'planned_start_date': tf.planned_start_date,
                        'planned_end_date': tf.planned_end_date,
                    })
            
        # Sync to timeline chart
        self._create_timeline_formats()
            
        return True


    def create_apqp_timeline_chart(self):
        for record in self:
            if not record.apqp_timeline_chart_id:
                apqp_timeline_chart = self.env['apqp.timeline.chart'].create({
                    'document_package_id': record.id,
                    'partner_id': record.partner_id.id,
                    'used_in_project_type_id': record.used_in_project_type_id.id,
                })
                record.apqp_timeline_chart_id = apqp_timeline_chart.id
                # Populate attachments from templates
                apqp_timeline_chart.populate_attachments_from_templates()
                record._create_timeline_formats()
    
    def _create_timeline_formats(self):
        for record in self:
            if not (record.apqp_timeline_chart_id and record.document_approval_ids):
                continue
            timeline_chart = record.apqp_timeline_chart_id
            timeline_chart.timeline_format_ids.filtered(lambda x: not x.source_attachment_id).unlink()
            
            all_phases = self.env['apqp.phase'].search([], order='sequence')
            for phase in all_phases:
                self.env['apqp.timeline.format'].create({
                    'timeline_chart_id': timeline_chart.id,
                    'name': phase.name,
                    'display_type': 'line_section',
                    'phase_id': phase.id,
                    'sequence': phase.sequence * 1000,
                })
            
            phases_with_approvals = record.document_approval_ids.mapped('phase_id').sorted('sequence')
            no_phase_approvals = record.document_approval_ids.filtered(lambda x: not x.phase_id)
            
            for phase in phases_with_approvals:
                phase_base_sequence = phase.sequence * 1000
                sequence_within_phase = 10
                phase_approvals = record.document_approval_ids.filtered(lambda x: x.phase_id == phase)
                for approval in phase_approvals.sorted('sr_no'):
                    if approval.formate:
                        self.env['apqp.timeline.format'].create({
                            'timeline_chart_id': timeline_chart.id,
                            'name': approval.formate.name,
                            'format_id': approval.formate.id,
                            'document_approval_id': approval.id,
                            'phase_id': phase.id,
                            'sequence': phase_base_sequence + sequence_within_phase,
                            'planned_start_date': approval.plan_start_date,
                            'planned_end_date': approval.plan_end_date,
                            'actual_start_date': approval.actual_start_date,
                            'actual_end_date': approval.actual_end_date,
                        })
                        sequence_within_phase += 10

            if no_phase_approvals:
                max_phase = all_phases[-1] if all_phases else None
                no_phase_sequence = (max_phase.sequence + 1) * 1000 if max_phase else 999000
                self.env['apqp.timeline.format'].create({
                    'timeline_chart_id': timeline_chart.id,
                    'name': 'No Phase Assigned',
                    'display_type': 'line_section',
                    'sequence': no_phase_sequence,
                })
                sequence_within_no_phase = 10
                for approval in no_phase_approvals.sorted('sr_no'):
                    if approval.formate:
                        self.env['apqp.timeline.format'].create({
                            'timeline_chart_id': timeline_chart.id,
                            'name': approval.formate.name,
                            'format_id': approval.formate.id,
                            'document_approval_id': approval.id,
                            'sequence': no_phase_sequence + sequence_within_no_phase,
                            'planned_start_date': approval.plan_start_date,
                            'planned_end_date': approval.plan_end_date,
                            'actual_start_date': approval.actual_start_date,
                            'actual_end_date': approval.actual_end_date,
                        })
                        sequence_within_no_phase += 10
            
            # Sync all attachments to ensure they have their format lines
            timeline_chart._sync_all_attachments()

    def action_open_apqp_timeline_chart(self):
        """Open the form view of the linked APQP Timeline Chart."""
        self.ensure_one()
        if not self.apqp_timeline_chart_id:
            raise UserError(_("No APQP Timeline Chart is linked to this document package."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'apqp.timeline.chart',
            'view_mode': 'form',
            'res_id': self.apqp_timeline_chart_id.id,
            'target': 'current',
        }

    def action_configure_phase_timeframes(self):
        """Initialize phase timeframes if missing and open the configure popup."""
        self.ensure_one()
        if not self.phase_timeframe_ids:
            phases = self.env['apqp.phase'].search([], order='sequence')
            timeframe_vals = []
            for phase in phases:
                timeframe_vals.append((0, 0, {
                    'phase_id': phase.id,
                    'duration_value': phase.default_duration_value,
                    'duration_unit': phase.default_duration_unit,
                }))
            if timeframe_vals:
                self.write({'phase_timeframe_ids': timeframe_vals})
        
        return {
            'name': _('Project Phase Timeframes'),
            'type': 'ir.actions.act_window',
            'res_model': 'apqp.project.phase.timeframe',
            'view_mode': 'list',
            'target': 'new',
            'domain': [('document_package_id', '=', self.id)],
            'context': {
                'default_document_package_id': self.id,
            },
        }

    @api.model
    def create(self, vals):
        record = super(DocumentPackageInherit, self).create(vals)
        # Populate phase timeframes from defaults
        phases = self.env['apqp.phase'].search([], order='sequence')
        timeframe_vals = []
        for phase in phases:
            timeframe_vals.append((0, 0, {
                'phase_id': phase.id,
                'duration_value': phase.default_duration_value,
                'duration_unit': phase.default_duration_unit,
            }))
        if timeframe_vals:
            record.write({'phase_timeframe_ids': timeframe_vals})
            
        record.create_apqp_timeline_chart()
        return record

    def select_all_formate(self):
        department_lst = []
        formate_ids = self.env['document.formate'].search([]).filtered(
            lambda f: self.used_in_project_type_id.id in f.used_in_project_type_ids.ids
        )
        for formate in formate_ids:
            for department in formate.department_ids:
                manager = department.filtered(lambda l: not l.manager_id or not l.manager_id.work_email)
                if manager and department.name not in department_lst:
                    department_lst.append(department.name)

        if department_lst:
            raise UserError(_('Please configure Department Manager and their Email IDs in following departments:\n\n  %s') % ', '.join(department_lst))
        self.is_select_all = True
        for rec in formate_ids:
            manager_ids = rec.department_ids.mapped('manager_id').ids
            vals = {
                'serial_no': rec.serial_no,
                'sr_no': rec.sr_no,
                'control_emp_ids': [(6, 0, rec.control_emp_ids.ids)],
                'used_in_project_type_ids': [(6, 0, rec.used_in_project_type_ids.ids)],
                'control_department_ids': [(6, 0, rec.control_department_ids.ids)],
                'formate': rec.id,
                'document_package_id': self.id,
                'department_ids': [(6, 0, rec.department_ids.ids)],
                'manager_ids': [(6, 0, manager_ids)],
                'phase_id': rec.phase_id.id if rec.phase_id else False,
            }
            self.env['document.approval'].create(vals)
        
        self.create_apqp_timeline_chart()
        # Populate attachments from templates when creating from select_all_formate
        if self.apqp_timeline_chart_id:
            self.apqp_timeline_chart_id.populate_attachments_from_templates()
        self._create_timeline_formats()
        # Apply phase dates after selecting formats
        self.action_update_phase_dates()
        return True
    
    def write(self, vals):
        res = super(DocumentPackageInherit, self).write(vals)
        
        # Define fields that should trigger a header sync to the timeline chart
        sync_fields = [
            'name', 'partner_id', 'used_in_project_type_id', 'start_date', 
            'target_date', 'project_start_date', 'project_end_date', 
            'doc_type', 'part_id', 'cft_team', 'description',
            'document_approval_ids'
        ]
        
        # Check if any of the sync fields have changed
        if any(field in vals for field in sync_fields):
            for record in self:
                if record.apqp_timeline_chart_id:
                    record.apqp_timeline_chart_id.refresh_data_from_package()
        
        if 'document_approval_ids' in vals:
            self._create_timeline_formats()
        return res