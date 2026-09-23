# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class APQPPhase(models.Model):
    _name = 'apqp.phase'
    _description = 'APQP Phase'
    _order = 'sequence, id'

    name = fields.Char(string='Phase Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')
    color = fields.Integer(string='Color Index')
    active = fields.Boolean(string='Active', default=True)
    default_duration_value = fields.Integer(string='Default Duration')
    default_duration_unit = fields.Selection([
        ('days', 'Days'),
        ('weeks', 'Weeks')
    ], string='Duration Unit', default='weeks')
    gate_review_id = fields.Many2one('gate.review', string='Gate Review')

    @api.depends('name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.name
