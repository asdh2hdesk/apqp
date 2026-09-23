# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date


class APQPTimelineChart(models.Model):
    _name = 'apqp.timeline.chart'
    _description = 'APQP Timeline Chart'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # _rec_name = 'name'

    # Main Fields from Document Package
    name  = fields.Char(string='Name', compute='_compute_name', store=True, readonly=False)
    project_name = fields.Char(string='Project Name', required=True, tracking=True)
    document_package_id = fields.Many2one('xf.doc.approval.document.package', string='Document Package', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Customer Name', tracking=True)
    used_in_project_type_id = fields.Many2one('doc.project.type', string='Project Type', default=lambda self: self.env.ref('xf_doc_approval.doc_project_type_1', raise_if_not_found=False))
    
    # Date Fields
    start_date = fields.Date('Start Date', default=date.today(), tracking=True)
    target_date = fields.Date('Target Date', tracking=True)
    project_start_date = fields.Date('Actual Start Date', tracking=True)
    project_end_date = fields.Date('Actual End Date', tracking=True)
    
    # Document Type and Part Information
    doc_type = fields.Selection([
        ('safelaunch', 'Safe Launch'), 
        ('prototype', 'Prototype'), 
        ('prelaunch', 'PreLaunch'),
        ('production', 'Production')
    ], string='Document Type', tracking=True)
    
    part_id = fields.Many2one("product.template", string="Part")
    part_name = fields.Char("Part Name", related="part_id.name", store=True)
    part_number = fields.Char("Part Number", related="part_id.default_code", store=True)
    drawing_no = fields.Char("Drawing No.", related="part_id.drg_no", store=True)
    cft_team = fields.Many2many('res.users', string='CFT Team')
    description = fields.Text(string='Description')
    
    # Timeline Format Lines
    timeline_format_ids = fields.One2many('apqp.timeline.format', 'timeline_chart_id', string='Timeline Formats')
    
    # Attachment Lines
    attachment_ids = fields.One2many('apqp.timeline.attachment', 'timeline_chart_id', string='Attachments')
    
    # MOM Format Lines
    mom_format_ids = fields.One2many('apqp.mom.format', 'timeline_chart_id', string='MOM Formats')
    
    # Attendees and Conducted By fields for automatic MOM data transfer
    attendee_ids = fields.Many2many('hr.employee', 'apqp_timeline_attendee_rel', 'timeline_id', 'employee_id', string='Default Attendees')
    conducted_by_id = fields.Many2one('hr.employee', string='Default Conducted By/Champion')
    
    # State Management
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', compute='_compute_state', store=True, tracking=True)

    @api.depends('progress')
    def _compute_state(self):
        for record in self:
            if record.state == 'cancelled':
                continue  # Don't override cancelled state
            if record.progress == 0:
                record.state = 'draft'
            elif record.progress >= 100:
                record.state = 'completed'
            else:
                record.state = 'in_progress'
    
    # Computed Fields
    progress = fields.Float(string='Progress (%)', compute='_compute_progress', store=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    timeline_html = fields.Html(string='Timeline Overview', compute='_compute_timeline_html', sanitize=False)
    
    @api.depends('project_name')
    def _compute_name(self):
        """Compute the name field based on project name."""
        for record in self:
            record.name = f"{record.project_name} Timeline Chart"
    
    @api.depends('project_name')
    def _compute_display_name(self):
        """Customize the display name to include 'Timeline Chart'."""
        for record in self:
            record.display_name = f"{record.project_name} Timeline Chart"
    
    @api.depends('timeline_format_ids.actual_start_date', 'timeline_format_ids.actual_end_date')
    def _compute_progress(self):
        for record in self:
            if record.timeline_format_ids:
                total = len(record.timeline_format_ids.filtered(lambda l: not l.display_type))
                completed = len(record.timeline_format_ids.filtered(lambda l: l.actual_end_date and not l.display_type))
                record.progress = (completed / total) * 100 if total > 0 else 0.0
            else:
                record.progress = 0.0
    
    @api.depends('timeline_format_ids', 'timeline_format_ids.phase_id', 'timeline_format_ids.name',
                 'timeline_format_ids.planned_start_date', 'timeline_format_ids.planned_end_date',
                 'timeline_format_ids.actual_start_date', 'timeline_format_ids.actual_end_date',
                 'timeline_format_ids.status', 'timeline_format_ids.reference',
                 'timeline_format_ids.sequence', 'timeline_format_ids.display_type')
    def _compute_timeline_html(self):
        for record in self:
            if not record.timeline_format_ids:
                record.timeline_html = "<p>No timeline data available.</p>"
                continue
            
            # Build HTML table
            html_content = """
            <style>
                .timeline-table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                    font-family: Arial, sans-serif;
                }
                .timeline-table th {
                    background-color: #e6f3ff;
                    padding: 10px;
                    text-align: left;
                    border: 1px solid #ddd;
                    font-weight: bold;
                }
                .timeline-table td {
                    padding: 8px;
                    border: 1px solid #ddd;
                    text-align: left;
                }
                .phase-header {
                    background-color: #f0f8ff;
                    font-weight: bold;
                    color: #0066cc;
                }
                .format-row {
                    background-color: #ffffff;
                }
                .format-row:hover {
                    background-color: #f5f5f5;
                }
                .status-completed {
                    background-color: #d4edda;
                    color: #155724;
                    padding: 3px 8px;
                    border-radius: 3px;
                    display: inline-block;
                }
                .status-in_progress {
                    background-color: #fff3cd;
                    color: #856404;
                    padding: 3px 8px;
                    border-radius: 3px;
                    display: inline-block;
                }
                .status-delayed {
                    background-color: #f8d7da;
                    color: #721c24;
                    padding: 3px 8px;
                    border-radius: 3px;
                    display: inline-block;
                }
                .status-not_started {
                    background-color: #e2e3e5;
                    color: #383d41;
                    padding: 3px 8px;
                    border-radius: 3px;
                    display: inline-block;
                }
            </style>
            <div style="overflow-x: auto;">
                <table class="timeline-table">
                    <thead>
                        <tr>
                            <th style="width: 200px;">Phase</th>
                            <th style="width: 250px;">Format Name</th>
                            <th>Reference</th>
                            <th>Planned Start</th>
                            <th>Planned End</th>
                            <th>Actual Start</th>
                            <th>Actual End</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            # Get all timeline formats sorted by sequence
            timeline_formats = record.timeline_format_ids.sorted('sequence')
            current_phase = None
            
            for format_line in timeline_formats:
                # Check if this is a section line
                if format_line.display_type == 'line_section':
                    current_phase = format_line.phase_id
                    # Add phase header row
                    html_content += f"""
                        <tr class="phase-header">
                            <td colspan="8">{format_line.name or (format_line.phase_id.name if format_line.phase_id else 'No Phase')}</td>
                        </tr>
                    """
                elif not format_line.display_type:  # Regular format line
                    status_display = dict(format_line._fields['status'].selection).get(format_line.status, '')
                    status_class = f"status-{format_line.status}" if format_line.status else ""
                    
                    html_content += f"""
                    <tr class="format-row">
                        <td></td>
                        <td>{format_line.name or ''}</td>
                        <td>{format_line.reference or ''}</td>
                        <td>{format_line.planned_start_date or ''}</td>
                        <td>{format_line.planned_end_date or ''}</td>
                        <td>{format_line.actual_start_date or ''}</td>
                        <td>{format_line.actual_end_date or ''}</td>
                        <td><span class="{status_class}">{status_display}</span></td>
                    </tr>
                    """
            
            html_content += """
                    </tbody>
                </table>
            </div>
            """
            
            record.timeline_html = html_content
    
    def action_view_timeline_chart(self):
        """Action to open the Timeline Chart view, grouped by phase with formats under sections."""
        self.ensure_one()
        return {
            'name': _('APQP Timeline Chart - %s' % self.project_name),
            'type': 'ir.actions.act_window',
            'res_model': 'apqp.timeline.format',
            'view_mode': 'list,form,pivot',
            'domain': [('timeline_chart_id', '=', self.id)],
            'context': {
                'default_timeline_chart_id': self.id,
                'group_by': ['phase_id'],
                'search_default_group_by_phase': 1,
            },
            'views': [
                (self.env.ref('apqp.view_apqp_timeline_format_tree').id, 'list'),
                (self.env.ref('apqp.view_apqp_timeline_format_form').id, 'form'),
                (False, 'pivot'),
            ],
        }
    
    # def action_refresh_timeline(self):
    #     """Refresh the timeline HTML."""
    #     self._compute_timeline_html()
    #     return True
    
    def action_view_timeline_overview(self):
        """Open the timeline overview wizard."""
        self.ensure_one()
        return {
            'name': _('Timeline Overview - %s' % self.project_name),
            'type': 'ir.actions.act_window',
            'res_model': 'apqp.timeline.overview.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('apqp.apqp_timeline_overview_wizard_form').id,
            'target': 'new',
            'context': {
                'default_timeline_chart_id': self.id,
            },
        }
    
    def action_refresh_timeline(self):
        """Refresh the timeline HTML."""
        self._compute_timeline_html()
        self.populate_attachments_from_templates()
        return True
    
    def populate_attachments_from_templates(self):
        """Populate attachment_ids from format templates."""
        self.ensure_one()
        # Get all active format templates
        format_templates = self.env['apqp.format.template'].search([('active', '=', True)], order='sequence')
        
        for template in format_templates:
            # Check if attachment already exists
            existing_attachment = self.attachment_ids.filtered(
                lambda a: a.format_name == template.format_name and a.phase_id == template.phase_id
            )
            
            if not existing_attachment:
                # Get planned dates from document package if available
                planned_start = False
                planned_end = False
                if self.document_package_id:
                    timeframe = self.document_package_id.phase_timeframe_ids.filtered(lambda x: x.phase_id == template.phase_id)
                    if timeframe:
                        planned_start = timeframe[0].planned_start_date
                        planned_end = timeframe[0].planned_end_date
                
                self.env['apqp.timeline.attachment'].create({
                    'timeline_chart_id': self.id,
                    'format_name': template.format_name,
                    'phase_id': template.phase_id.id,
                    'sequence': template.sequence,
                    'planned_start_date': planned_start,
                    'planned_end_date': planned_end,
                    'input_field': template.input_field,
                    'output_field': template.output_field,
                    'activity': template.activity,
                    'document_type': template.document_type,
                    'department_ids': [(6, 0, template.department_ids.ids)],
                })
        
        return True
    
    def refresh_data_from_package(self):
        """Fetch data from document package and update header fields."""
        for record in self:
            if record.document_package_id:
                doc = record.document_package_id
                record.write({
                    'project_name': doc.name,
                    'partner_id': doc.partner_id.id,
                    'used_in_project_type_id': doc.used_in_project_type_id.id,
                    'start_date': doc.start_date,
                    'target_date': doc.target_date,
                    'project_start_date': doc.project_start_date,
                    'project_end_date': doc.project_end_date,
                    'doc_type': doc.doc_type,
                    'part_id': doc.part_id.id,
                    'cft_team': [(6, 0, doc.cft_team.ids)],
                    'description': doc.description,
                })
        return True

    @api.onchange('document_package_id')
    def _onchange_document_package_id(self):
        """Fetch data from document package when it's selected in the UI."""
        if self.document_package_id:
            doc = self.document_package_id
            self.project_name = doc.name
            self.partner_id = doc.partner_id
            self.used_in_project_type_id = doc.used_in_project_type_id
            self.start_date = doc.start_date
            self.target_date = doc.target_date
            self.project_start_date = doc.project_start_date
            self.project_end_date = doc.project_end_date
            self.doc_type = doc.doc_type
            self.part_id = doc.part_id
            self.cft_team = [(6, 0, doc.cft_team.ids)]
            self.description = doc.description

    @api.model
    def create(self, vals):
        """Override create to copy data from document package."""
        if 'document_package_id' in vals:
            doc_package = self.env['xf.doc.approval.document.package'].browse(vals['document_package_id'])
            vals.update({
                'project_name': doc_package.name,
                'partner_id': doc_package.partner_id.id,
                'used_in_project_type_id': doc_package.used_in_project_type_id.id,
                'start_date': doc_package.start_date,
                'target_date': doc_package.target_date,
                'project_start_date': doc_package.project_start_date,
                'project_end_date': doc_package.project_end_date,
                'doc_type': doc_package.doc_type,
                'part_id': doc_package.part_id.id,
                'cft_team': [(6, 0, doc_package.cft_team.ids)],
                'description': doc_package.description,
            })
        timeline_chart = super(APQPTimelineChart, self).create(vals)
        # Sync attachments after creation
        timeline_chart._sync_all_attachments()
        return timeline_chart
    
    def write(self, vals):
        """Override write to ensure attachments are synced."""
        res = super(APQPTimelineChart, self).write(vals)
        # Only sync attachments if we're not already in a sync operation
        if not self.env.context.get('skip_sync'):
            self.with_context(skip_sync=True)._sync_all_attachments()
        return res
    
    def _sync_all_attachments(self):
        """Sync all attachments to timeline formats."""
        for record in self:
            # Ensure basic structure (Phases and Gates)
            record._ensure_timeline_structure()
            # Sync each attachment
            for attachment in record.attachment_ids:
                attachment._sync_to_timeline_format()

    def _ensure_timeline_structure(self):
        """Ensure all phases and their gate reviews exist as lines in the timeline."""
        for record in self:
            all_phases = self.env['apqp.phase'].search([], order='sequence')
            for phase in all_phases:
                # 1. Ensure Phase Section exists
                existing_section = self.env['apqp.timeline.format'].search([
                    ('timeline_chart_id', '=', record.id),
                    ('phase_id', '=', phase.id),
                    ('display_type', '=', 'line_section')
                ], limit=1)

                if not existing_section:
                    self.env['apqp.timeline.format'].with_context(from_attachment_sync=True).create({
                        'timeline_chart_id': record.id,
                        'phase_id': phase.id,
                        'display_type': 'line_section',
                        'name': phase.name,
                        'sequence': phase.sequence * 1000,
                    })

                # 2. Ensure Gate Review exists if phase has one
                gate_review = phase.gate_review_id
                if not gate_review:
                    # Fallback: Try to find by name if the data link is broken
                    search_name = phase.name.split(':')[0].replace('Phase', 'Gate') + ' Review'
                    gate_review = self.env['gate.review'].search([('name', 'ilike', search_name)], limit=1)
                    if gate_review:
                        phase.gate_review_id = gate_review.id

                if gate_review:
                    gate_format = self.env['apqp.timeline.format'].search([
                        ('timeline_chart_id', '=', record.id),
                        ('phase_id', '=', phase.id),
                        ('is_gate_review', '=', True)
                    ], limit=1)

                    if not gate_format:
                        self.env['apqp.timeline.format'].with_context(from_attachment_sync=True).create({
                            'timeline_chart_id': record.id,
                            'phase_id': phase.id,
                            'name': gate_review.name,
                            'sequence': (phase.sequence * 1000) + 9999, # Use 9999 to be really sure it is last
                            'is_gate_review': True,
                            'gate_review_id': gate_review.id,
                            'activity': 'Gate Review',
                            'document_type': 'confirmation',
                        })
                    else:
                        # Update gate review info if needed
                        gate_format.with_context(from_attachment_sync=True).write({
                            'name': gate_review.name,
                            'gate_review_id': gate_review.id,
                            'sequence': (phase.sequence * 1000) + 9999,
                            'activity': 'Gate Review',
                            'document_type': 'confirmation',
                        })
    
    