# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class APQPTimelineFormat(models.Model):
    _name = 'apqp.timeline.format'
    _description = 'APQP Timeline Format'
    _order = 'sequence, id'

    timeline_chart_id = fields.Many2one('apqp.timeline.chart', string='Timeline Chart', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    
    # Format Information
    name = fields.Char(string='Format Name', required=True)
    format_id = fields.Many2one('document.formate', string='Document Format')
    document_approval_id = fields.Many2one('document.approval', string='Document Approval')
    activity = fields.Char(string='Activity', help='Activity associated with this format.')
    parent_activity_id = fields.Many2one(
        'apqp.timeline.format',
        string='Parent Activity',
        domain="[('timeline_chart_id', '=', timeline_chart_id), ('display_type', '=', False)]",
        help='Parent activity if this is a trial/sub-activity of another line.'
    )

    document_type = fields.Selection([
        ('format', 'Format'),
        ('confirmation', 'Confirmation Only'),
        ('attachment', 'Add Attachment')
    ], string='Document Type', 
        help='Select whether this requires confirmation only or attachment upload.')
    
    # Phase Information
    phase_id = fields.Many2one('apqp.phase', string='Phase')
    
    # Date Fields
    planned_start_date = fields.Date(string='Planned Start Date')
    planned_end_date = fields.Date(string='Planned End Date')
    actual_start_date = fields.Date(string='Actual Start Date')
    actual_end_date = fields.Date(string='Actual End Date')

    # Duration Fields
    planned_duration = fields.Integer(
        string='Planned Duration (Days)',
        compute='_compute_planned_duration',
        store=True,
        help='Number of days between Planned Start Date and Planned End Date.'
    )
    actual_duration = fields.Integer(
        string='Actual Duration (Days)',
        compute='_compute_actual_duration',
        store=True,
        help='Number of days between Actual Start Date and Actual End Date.'
    )

    # Status and Progress
    status = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('delayed', 'Delayed')
    ], string='Status', default='not_started', compute='_compute_status', store=True)

    # Display Type for Sections and Notes
    display_type = fields.Selection([
        ('line_section', 'Section'),
        ('line_note', 'Note')
    ], string='Display Type', help='Technical field for UX purpose.')

    # Computed field to show phase name in section lines
    section_name = fields.Char(string='Section Name', compute='_compute_section_name', store=True)

    # Attachments
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    attachment_count = fields.Integer(string='Attachment Count', compute='_compute_attachment_count')

    # Additional Fields
    reference = fields.Char(string='Reference')
    is_gate_review = fields.Boolean(string='Is Gate Review', default=False)
    gate_review_id = fields.Many2one('gate.review', string='Gate Review')
    notes = fields.Text(string='Notes')
    responsible_user_id = fields.Many2one('res.users', string='Responsible User')
    source_attachment_id = fields.Many2one('apqp.timeline.attachment', string='Source Attachment',
                                           help='If this format was created from an attachment')

    include_in_report = fields.Boolean(
        string='Include in Report',
        default=True,
    )

    # Input and Output fields
    input_field = fields.Html(string='Input', help='Input specifications or requirements for this format.')
    output_field = fields.Html(string='Output', help='Output specifications or deliverables for this format.')
    department_ids = fields.Many2many('hr.department', 'apqp_timeline_format_department_rel', string='Departments',
                                      help='Departments responsible for this task.')

    @api.depends('planned_start_date', 'planned_end_date')
    def _compute_planned_duration(self):
        for record in self:
            if record.planned_start_date and record.planned_end_date:
                delta = record.planned_end_date - record.planned_start_date
                record.planned_duration = delta.days
            else:
                record.planned_duration = 0

    @api.depends('actual_start_date', 'actual_end_date')
    def _compute_actual_duration(self):
        for record in self:
            if record.actual_start_date and record.actual_end_date:
                delta = record.actual_end_date - record.actual_start_date
                record.actual_duration = delta.days
            else:
                record.actual_duration = 0

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for record in self:
            record.attachment_count = len(record.attachment_ids)

    @api.depends('phase_id', 'display_type')
    def _compute_section_name(self):
        for record in self:
            if record.display_type == 'line_section' and record.phase_id:
                record.section_name = record.phase_id.name
            else:
                record.section_name = False

    @api.depends('actual_start_date', 'actual_end_date', 'planned_end_date')
    def _compute_status(self):
        today = fields.Date.today()
        for record in self:
            if record.display_type:
                record.status = False  # Sections and notes don't have status
            elif record.actual_end_date:
                record.status = 'completed'
            elif record.actual_start_date:
                if record.planned_end_date and today > record.planned_end_date:
                    record.status = 'delayed'
                else:
                    record.status = 'in_progress'
            else:
                record.status = 'not_started'

    @api.onchange('format_id')
    def _onchange_format_id(self):
        if self.format_id:
            self.name = self.format_id.name
            self.document_type = 'format'

    def action_view_attachments(self):
        self.ensure_one()
        return {
            'name': _('Attachments'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', self.attachment_ids.ids)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
        }

    def action_insert_below(self):
        self.ensure_one()
        parent = self.timeline_chart_id
        current_seq = self.sequence

        # Shift every row after this one up by 1
        siblings_after = parent.timeline_format_ids.filtered(
            lambda r: r.id != self.id and r.sequence > current_seq
        )
        for sib in siblings_after:
            sib.sudo().write({'sequence': sib.sequence + 1})

        self.env['apqp.timeline.format'].sudo().create({
            'timeline_chart_id': parent.id,
            'sequence': current_seq + 1,
            'name': 'New Line',
            'display_type': False,
            'parent_activity_id': self.parent_activity_id.id or self.id,
        })

        return False

    def action_open_form(self):
        self.ensure_one()

        if self.source_attachment_id:
            return self.source_attachment_id.action_open_form()

        # Handle format type - open or create the linked document approval record
        if self.document_type == 'format' and self.document_approval_id:
            doc_approval = self.document_approval_id

            if doc_approval.formate_id and doc_approval.formate and doc_approval.formate.table:
                # Record exists - open it
                return {
                    'type': 'ir.actions.act_window',
                    'name': doc_approval.formate.name,
                    'view_mode': 'form',
                    'res_model': doc_approval.formate.table,
                    'res_id': int(doc_approval.formate_id),
                    'target': 'current',
                    'context': {'create': False},
                }
            elif doc_approval.formate and doc_approval.formate.table:
                # Record doesn't exist yet - create it
                return doc_approval.create_formate()

        return False

    def action_add_attachment(self):
        self.ensure_one()
        return {
            'name': _('Add Attachment'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
        }
    @api.model
    def create(self, vals):
        """Override create to ensure phase_id is set for sections."""
        # If creating a section and phase_id is provided, ensure the name is set
        if vals.get('format_id') and not vals.get('document_type'):
            vals['document_type'] = 'format'

        if vals.get('display_type') == 'line_section' and vals.get('phase_id'):
            phase = self.env['apqp.phase'].browse(vals['phase_id'])
            if phase and not vals.get('name'):
                vals['name'] = phase.name
        return super(APQPTimelineFormat, self).create(vals)

    def write(self, vals):
        """Override write to sync phase changes back to source attachment and handle sequencing."""
        # Handle sequence changes to automatically update phase_id
        if 'sequence' in vals and not 'phase_id' in vals:
            for record in self:
                if not record.display_type:  # Only for regular lines, not sections
                    # Find the nearest phase section above this sequence
                    phase_section = self.search([
                        ('timeline_chart_id', '=', record.timeline_chart_id.id),
                        ('display_type', '=', 'line_section'),
                        ('sequence', '<=', vals.get('sequence', record.sequence))
                    ], order='sequence desc', limit=1)

                    if phase_section and phase_section.phase_id != record.phase_id:
                        vals['phase_id'] = phase_section.phase_id.id

        # Update section name if phase_id changes
        if 'phase_id' in vals and self.filtered(lambda r: r.display_type == 'line_section'):
            phase = self.env['apqp.phase'].browse(vals['phase_id'])
            if phase:
                vals['name'] = phase.name

        res = super(APQPTimelineFormat, self).write(vals)

        # If phase_id changed and this format has a source attachment, update it
        if 'phase_id' in vals:
            for record in self:
                if record.source_attachment_id and not record.display_type:
                    # Update the source attachment's phase
                    record.source_attachment_id.with_context(skip_sync=True).write({
                        'phase_id': record.phase_id.id
                    })

        # Sync sequence changes back to source attachment
        if 'sequence' in vals and not self.env.context.get('from_attachment_sync'):
            for record in self:
                if record.source_attachment_id and not record.display_type:
                    # Calculate relative sequence within the phase
                    phase_section = self.search([
                        ('timeline_chart_id', '=', record.timeline_chart_id.id),
                        ('phase_id', '=', record.phase_id.id),
                        ('display_type', '=', 'line_section')
                    ], limit=1)
                    relative_sequence = record.sequence - (phase_section.sequence if phase_section else 0)
                    record.source_attachment_id.with_context(skip_sync=True).write({
                        'sequence': relative_sequence
                    })

        # Sync changes from source attachment
        if any(field in vals for field in
               ['planned_start_date', 'planned_end_date', 'actual_start_date', 'actual_end_date', 'reference',
                'input_field', 'output_field', 'department_ids', 'activity', 'document_type']):
            for record in self:
                if record.source_attachment_id and not self.env.context.get('from_attachment_sync'):
                    sync_vals = {}
                    for field in ['planned_start_date', 'planned_end_date', 'actual_start_date', 'actual_end_date',
                                  'reference', 'input_field', 'output_field', 'department_ids', 'activity',
                                  'document_type']:
                        if field in vals:
                            if field == 'department_ids':
                                sync_vals[field] = vals[field]  # Already in (6, 0, ids) format usually
                            else:
                                sync_vals[field] = vals[field]
                    if sync_vals:
                        record.source_attachment_id.with_context(skip_sync=True).write(sync_vals)

        return res