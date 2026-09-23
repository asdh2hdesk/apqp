# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class APQPTimelineAttachment(models.Model):
    _name = 'apqp.timeline.attachment'
    _description = 'APQP Timeline Attachment'
    _order = 'sequence, id'

    # Core relational fields
    timeline_chart_id = fields.Many2one('apqp.timeline.chart', string='Timeline Chart', ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10,
                              help='Defines the order of this attachment in the timeline.')

    # Attachment-specific information
    name = fields.Char(string='Description', help='A brief description of the attachment.')
    phase_id = fields.Many2one('apqp.phase', string='Phase', required=True,
                               help='The phase this attachment belongs to.')
    format_name = fields.Char(string='Format Name', required=True,
                              help='Name of the format this attachment represents.')
    activity = fields.Char(string='Activity', help='Activity associated with this format.')

    # Document Type Selection
    document_type = fields.Selection([
        ('confirmation', 'Confirmation Only'),
        ('attachment', 'Add Attachment')
    ], string='Document Type', required=True,
        help='Select whether this requires confirmation only or attachment upload.')

    # Date fields for planning and tracking
    planned_start_date = fields.Date(string='Planned Start Date')
    planned_end_date = fields.Date(string='Planned End Date')
    actual_start_date = fields.Date(string='Actual Start Date', compute='_compute_actual_dates', store=True)
    actual_end_date = fields.Date(string='Actual End Date', compute='_compute_actual_dates', store=True)

    # Attachment management
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments',
                                      help='Files attached to this timeline entry.')
    attachment_count = fields.Integer(string='Attachment Count', compute='_compute_attachment_count',
                                      help='Number of attached files.')

    # Document Tracking - User Approvals
    prepared_by = fields.Many2one('res.users', string='Prepared By', readonly=True,
                                  help='User who uploaded/prepared the document.')
    prepared_date = fields.Datetime(string='Prepared Date', readonly=True,
                                    help='Date and time when document was prepared.')

    reviewed_by = fields.Many2one('res.users', string='Reviewed By',
                                  help='User who reviewed the document.')
    reviewed_date = fields.Datetime(string='Reviewed Date', readonly=True,
                                    help='Date and time when document was reviewed.')

    approved_by = fields.Many2one('res.users', string='Approved By',
                                  help='User who approved the document.')
    approved_date = fields.Datetime(string='Approved Date', readonly=True,
                                    help='Date and time when document was approved.')

    # Confirmation Boolean
    is_confirmed = fields.Boolean(string='Confirmed', default=False,
                                  help='Checkbox for confirmation type documents.')
    confirmed_date = fields.Datetime(string='Confirmed Date', readonly=True,
                                     help='Date and time when document was confirmed.')

    # Additional metadata
    reference = fields.Char(string='Reference', help='A reference code or identifier.')
    is_gate_review = fields.Boolean(string='Is Gate Review', default=False)
    gate_review_id = fields.Many2one('gate.review', string='Gate Review')
    input_field = fields.Html(string='Input', help='Input specifications or requirements for this format.')
    output_field = fields.Html(string='Output', help='Output specifications or deliverables for this format.')
    department_ids = fields.Many2many('hr.department', 'apqp_timeline_attachment_department_rel', string='Departments',
                                       help='Departments responsible for this task.')
    notes = fields.Text(string='Notes', help='Additional notes or comments.')
    state = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('delayed', 'Delayed')
    ], string='Status', default='not_started', compute='_compute_state', store=True,
        help='Current status of the attachment.')

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        """Calculate the number of attachments linked to this record."""
        for record in self:
            record.attachment_count = len(record.attachment_ids)

    @api.depends('prepared_date', 'approved_date', 'planned_end_date', 'is_confirmed', 'confirmed_date',
                 'document_type')
    def _compute_actual_dates(self):
        """Compute actual start and end dates based on approval workflow."""
        from datetime import datetime
        today = fields.Date.today()

        for record in self:
            # Set actual_start_date when prepared
            if record.prepared_date:
                record.actual_start_date = record.prepared_date.date() if isinstance(record.prepared_date,
                                                                                     datetime) else record.prepared_date
            else:
                record.actual_start_date = None

            # Set actual_end_date only when explicitly approved (not just auto-confirmed)
            if record.document_type == 'confirmation' and record.is_confirmed and record.confirmed_date:
                # For confirmation type: end date is when manually confirmed
                record.actual_end_date = record.confirmed_date.date() if isinstance(record.confirmed_date,
                                                                                    datetime) else record.confirmed_date
            elif record.document_type == 'attachment' and record.approved_date:
                # For attachment type: end date is only when APPROVED (not when auto-confirmed)
                record.actual_end_date = record.approved_date.date() if isinstance(record.approved_date,
                                                                                   datetime) else record.approved_date
            else:
                record.actual_end_date = None

    @api.depends('actual_start_date', 'actual_end_date', 'planned_end_date', 'prepared_date', 'approved_date')
    def _compute_state(self):
        """Compute the status based on date fields and approval workflow."""
        today = fields.Date.today()
        for record in self:
            if record.actual_end_date:
                # Only marked as completed if actual_end_date is set (which requires approval)
                record.state = 'completed'
            elif record.actual_start_date:
                # In progress if started
                if record.planned_end_date and today > record.planned_end_date:
                    record.state = 'delayed'
                else:
                    record.state = 'in_progress'
            else:
                # Not started if no start date
                record.state = 'not_started'

    @api.model
    def create(self, vals):
        """Create an attachment and sync it to the timeline format."""
        attachment = super(APQPTimelineAttachment, self).create(vals)
        attachment._sync_to_timeline_format()
        return attachment

    def _check_department_restriction(self):
        """Check if the current user belongs to the assigned departments."""
        if not self.department_ids:
            return True
        
        user_employee = self.env.user.employee_id
        if not user_employee:
            raise ValidationError(_("You must be linked to an employee record with a department to perform this action."))
            
        if user_employee.department_id.id not in self.department_ids.ids:
            dept_names = ", ".join(self.department_ids.mapped('name'))
            raise ValidationError(_("This task is restricted to the following departments: %s. Your department is %s.") % (dept_names, user_employee.department_id.name))
        
        return True

    def action_mark_prepared(self):
        """Mark document as prepared by current user."""
        self.ensure_one()
        self._check_department_restriction()
        if self.document_type == 'attachment' and not self.attachment_ids:
            raise ValidationError(_("Please upload at least one document before marking as prepared."))
        current_time = fields.Datetime.now()
        self.write({
            'prepared_by': self.env.user.id,
            'prepared_date': current_time,
        })
        return True

    def action_mark_reviewed(self):
        """Mark document as reviewed by current user."""
        self.ensure_one()
        self._check_department_restriction()
        current_time = fields.Datetime.now()
        self.write({
            'reviewed_by': self.env.user.id,
            'reviewed_date': current_time,
        })
        return True

    def action_mark_approved(self):
        """Mark document as approved by current user."""
        self.ensure_one()
        self._check_department_restriction()
        if self.document_type == 'confirmation' and not self.is_confirmed:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'message': _('Please confirm the document first before approving.'),
                    'type': 'warning',
                }
            }

        current_time = fields.Datetime.now()
        self.write({
            'approved_by': self.env.user.id,
            'approved_date': current_time,
        })
        return True

    def action_confirm_document(self):
        """Confirm document (for confirmation type only) with popup dialog."""
        self.ensure_one()
        self._check_department_restriction()
        if self.document_type != 'confirmation':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Info'),
                    'message': _('This is not a confirmation type document.'),
                    'type': 'info',
                }
            }

        # Show confirmation dialog
        return {
            'type': 'ir.actions.act_window',
            'name': _('Confirm Document'),
            'res_model': 'apqp.confirm.dialog',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_attachment_id': self.id,
                'default_format_name': self.format_name,
            }
        }

    def action_mark_attachment_added(self):
        """Auto-mark as prepared when attachment is added and auto-confirm for attachment type."""
        self.ensure_one()
        # self._check_department_restriction() # Usually this is called from UI when adding attachment, maybe too restrictive here?
        # But if the user says "only that department personal only we do that task", it should be here too.
        self._check_department_restriction()
        current_time = fields.Datetime.now()
        vals = {}

        # Always set prepared info when attachment is added
        if not self.prepared_by:
            vals['prepared_by'] = self.env.user.id
            vals['prepared_date'] = current_time

        # For attachment type, auto-confirm (but DON'T set actual_end_date)
        if self.document_type == 'attachment' and not self.is_confirmed:
            vals['is_confirmed'] = True
            vals['confirmed_date'] = current_time

        if vals:
            self.write(vals)
        return True

    def action_reset(self):
        """Reset all approval statuses."""
        self.ensure_one()
        self.write({
            'prepared_by': None,
            'prepared_date': None,
            'reviewed_by': None,
            'reviewed_date': None,
            'approved_by': None,
            'approved_date': None,
            'is_confirmed': False,
            'confirmed_date': None,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reset'),
                'message': _('All approval statuses have been reset.'),
                'type': 'success',
            }
        }

    def _sync_to_timeline_format(self):
        """Synchronize attachment data to a timeline format record with proper sequencing."""
        for attachment in self:
            if not (attachment.timeline_chart_id and attachment.phase_id and attachment.format_name):
                continue  # Skip if required fields are missing

            # Phase section for this attachment
            phase_section = self.env['apqp.timeline.format'].search([
                ('timeline_chart_id', '=', attachment.timeline_chart_id.id),
                ('phase_id', '=', attachment.phase_id.id),
                ('display_type', '=', 'line_section')
            ], limit=1)

            # Update the section name if it doesn't match the phase name
            if phase_section and phase_section.name != attachment.phase_id.name:
                phase_section.with_context(from_attachment_sync=True).write({'name': attachment.phase_id.name})

            # Look for an existing timeline format linked to this attachment
            existing_format = self.env['apqp.timeline.format'].search([
                ('timeline_chart_id', '=', attachment.timeline_chart_id.id),
                ('phase_id', '=', attachment.phase_id.id),
                ('name', '=', attachment.format_name),
                ('display_type', '=', False),
                ('source_attachment_id', '=', attachment.id)
            ], limit=1)

            # Calculate sequence for format line within the phase
            phase_base_sequence = attachment.phase_id.sequence * 1000
            # Get the next available sequence within this phase
            max_format_sequence = self.env['apqp.timeline.format'].search([
                ('timeline_chart_id', '=', attachment.timeline_chart_id.id),
                ('phase_id', '=', attachment.phase_id.id),
                ('display_type', '=', False),
                ('sequence', '>', phase_base_sequence),
                ('sequence', '<', phase_base_sequence + 1000)
            ], order='sequence desc', limit=1).sequence or phase_base_sequence

            next_sequence = max_format_sequence + 10

            # Values to sync to the timeline format
            format_vals = {
                'timeline_chart_id': attachment.timeline_chart_id.id,
                'phase_id': attachment.phase_id.id,
                'name': attachment.format_name,
                'planned_start_date': attachment.planned_start_date,
                'planned_end_date': attachment.planned_end_date,
                'actual_start_date': attachment.actual_start_date,
                'actual_end_date': attachment.actual_end_date,
                'reference': attachment.reference,
                'input_field': attachment.input_field,
                'output_field': attachment.output_field,
                'activity': attachment.activity,
                'document_type': attachment.document_type,
                'department_ids': [(6, 0, attachment.department_ids.ids)],
                'source_attachment_id': attachment.id,
                'is_gate_review': attachment.is_gate_review,
                'gate_review_id': attachment.gate_review_id.id,
            }

            if not existing_format:
                # Create a new timeline format if none exists
                format_vals['sequence'] = attachment.sequence + (phase_section.sequence if phase_section else 0)
                self.env['apqp.timeline.format'].with_context(from_attachment_sync=True).create(format_vals)
            else:
                # Update the existing format, but preserve its sequence
                existing_format.with_context(from_attachment_sync=True).write(format_vals)

    def write(self, vals):
        """Update the attachment and sync changes to the timeline format."""
        if self.env.context.get('skip_sync'):
            return super(APQPTimelineAttachment, self).write(vals)

        old_values = {}
        if 'phase_id' in vals or 'format_name' in vals:
            for attachment in self:
                old_values[attachment.id] = {
                    'phase_id': attachment.phase_id.id,
                    'format_name': attachment.format_name,
                }

        res = super(APQPTimelineAttachment, self).write(vals)

        for attachment in self:
            if attachment.id in old_values:
                old_phase_id = old_values[attachment.id]['phase_id']
                old_format_name = old_values[attachment.id]['format_name']

                # Remove old format if phase or format name changed
                if (old_phase_id != attachment.phase_id.id or
                        old_format_name != attachment.format_name):
                    old_format = self.env['apqp.timeline.format'].search([
                        ('timeline_chart_id', '=', attachment.timeline_chart_id.id),
                        ('phase_id', '=', old_phase_id),
                        ('name', '=', old_format_name),
                        ('display_type', '=', False),
                        ('source_attachment_id', '=', attachment.id)
                    ], limit=1)
                    if old_format:
                        old_format.unlink()

            # Sync updated data to timeline format
            attachment._sync_to_timeline_format()

        # Update gate review lines if phase_id or gate review links might have changed
        if 'phase_id' in vals:
            for attachment in self:
                if attachment.timeline_chart_id:
                    # This will trigger the loop in _sync_to_timeline_format that ensures all phases and gates exist
                    attachment._sync_to_timeline_format()

        return res

    def action_open_form(self):
        """Open the full form view of the attachment."""
        self.ensure_one()
        return {
            'name': _('APQP Timeline Attachment'),
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_attachments(self):
        """Open the attachments window."""
        self.ensure_one()
        action = {
            'name': _('Attachments'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.attachment_ids.ids)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
        }
        return action

    def unlink(self):
        """Delete the attachment and its corresponding timeline format if applicable."""
        formats_to_delete = self.env['apqp.timeline.format']

        for attachment in self:
            if attachment.timeline_chart_id and attachment.phase_id and attachment.format_name:
                timeline_format = self.env['apqp.timeline.format'].search([
                    ('timeline_chart_id', '=', attachment.timeline_chart_id.id),
                    ('phase_id', '=', attachment.phase_id.id),
                    ('name', '=', attachment.format_name),
                    ('display_type', '=', False),
                    ('source_attachment_id', '=', attachment.id)
                ], limit=1)
                # Only delete if no other attachments share this format
                if timeline_format and not self.search([
                    ('timeline_chart_id', '=', attachment.timeline_chart_id.id),
                    ('phase_id', '=', attachment.phase_id.id),
                    ('format_name', '=', attachment.format_name),
                    ('id', '!=', attachment.id)
                ]):
                    formats_to_delete |= timeline_format

        res = super(APQPTimelineAttachment, self).unlink()
        if formats_to_delete:
            formats_to_delete.unlink()

        return res


class APQPConfirmDialog(models.TransientModel):
    """Transient model for confirmation dialog."""
    _name = 'apqp.confirm.dialog'
    _description = 'Document Confirmation Dialog'

    attachment_id = fields.Many2one('apqp.timeline.attachment', string='Document')
    format_name = fields.Char(string='Format Name', readonly=True)

    def action_confirm(self):
        """Confirm the document."""
        self.ensure_one()
        current_time = fields.Datetime.now()
        self.attachment_id.write({
            'is_confirmed': True,
            'confirmed_date': current_time,
            'prepared_by': self.env.user.id,
            'prepared_date': current_time,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Document confirmed successfully.'),
                'type': 'success',
            }
        }