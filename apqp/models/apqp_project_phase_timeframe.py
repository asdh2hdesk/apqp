# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import timedelta

class APQPProjectPhaseTimeframe(models.Model):
    _name = 'apqp.project.phase.timeframe'
    _description = 'APQP Project Phase Timeframe'
    _order = 'sequence, id'

    document_package_id = fields.Many2one('xf.doc.approval.document.package', string='Document Package', ondelete='cascade', required=True)
    phase_id = fields.Many2one('apqp.phase', string='Phase', required=True)
    sequence = fields.Integer(related='phase_id.sequence', store=True)
    
    duration_value = fields.Integer(string='Duration')
    duration_unit = fields.Selection([
        ('days', 'Days'),
        ('weeks', 'Weeks')
    ], string='Unit', default='weeks')
    
    planned_start_date = fields.Date(string='Planned Start Date', readonly=True)
    planned_end_date = fields.Date(string='Planned End Date', readonly=True)

    @api.onchange('phase_id')
    def _onchange_phase_id(self):
        if self.phase_id:
            self.duration_value = self.phase_id.default_duration_value
            self.duration_unit = self.phase_id.default_duration_unit
            
    def write(self, vals):
        res = super(APQPProjectPhaseTimeframe, self).write(vals)
        if any(f in vals for f in ['duration_value', 'duration_unit']):
            # Trigger target_date recalculation on parent
            for record in self:
                if record.document_package_id:
                    record.document_package_id._compute_apqp_target_date()
        return res
