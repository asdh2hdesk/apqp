# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class DocumentApprovalInherit(models.Model):
    _inherit = 'document.approval'

    phase_id = fields.Many2one('apqp.phase', string='Phase')
    
    # Redefine fields to add state-based readonly if necessary, or do it in XML.
    # The requirement says "once the project is created no more plan date should be changed".
    # Usually "created" means it exists, but in Odoo context it often means when it starts moving from Draft.

    
    @api.onchange('formate')
    def _onchange_formate_phase(self):
        """Inherit phase from format when format is selected"""
        if self.formate and self.formate.phase_id:
            self.phase_id = self.formate.phase_id
    
    @api.model
    def create(self, vals):
        """Override create to sync with APQP timeline"""
        record = super(DocumentApprovalInherit, self).create(vals)
        # Create corresponding timeline format if APQP chart exists
        if record.document_package_id and record.document_package_id.apqp_timeline_chart_id:
            record.document_package_id._create_timeline_formats()
        return record
    
    def write(self, vals):
        """Override write to sync phase changes with timeline formats"""
        res = super(DocumentApprovalInherit, self).write(vals)
        if 'phase_id' in vals:
            for record in self:
                if record.document_package_id and record.document_package_id.apqp_timeline_chart_id:
                    timeline_formats = record.document_package_id.apqp_timeline_chart_id.timeline_format_ids.filtered(
                        lambda x: x.document_approval_id == record
                    )
                    if timeline_formats:
                        timeline_formats.write({'phase_id': vals['phase_id']})
        return res
    