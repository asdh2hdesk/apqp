# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class APQPFormatTemplate(models.Model):
    _name = 'apqp.format.template'
    _description = 'APQP Format Template'
    _order = 'sequence, id'
    _rec_name = 'format_name'

    sequence = fields.Integer(string='Sequence', default=15)
    format_name = fields.Char(string='Format Name', required=True)
    phase_id = fields.Many2one('apqp.phase', string='Phase', required=True)

    activity = fields.Char(string='Activity',required=True)
    document_type = fields.Selection([
        ('confirmation', 'Confirmation Only'),
        ('attachment', 'Add Attachment')
    ], string='Document Type', required=True, default='attachment',
        help='Select whether this requires confirmation only or attachment upload.')
    # Department support
    department_ids = fields.Many2many('hr.department', 'apqp_format_template_department_rel', string='Departments')

    # Input and Output fields
    input_field = fields.Html(string='Input', help='Input specifications or requirements for this format.')
    output_field = fields.Html(string='Output', help='Output specifications or deliverables for this format.')

    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('format_phase_uniq', 'unique (format_name, phase_id)',
         'The combination of format name and phase must be unique!')
    ]