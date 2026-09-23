from odoo import models, fields

# Gate
class GateReview(models.Model):
    _name = 'gate.review'
    _description = 'Gate Review'

    name = fields.Char(string="Gate Name", required=True)

    point_ids = fields.One2many(
        'gate.review.point',
        'gate_id',
        string="Points"
    )


# Point Master (NEW)
class GatePointMaster(models.Model):
    _name = 'gate.point.master'
    _description = 'Gate Point Master'

    name = fields.Char(string="Point Name", required=True)


# Gate लाइन (Points inside Gate)
class GateReviewPoint(models.Model):
    _name = 'gate.review.point'
    _description = 'Gate Review Points'

    gate_id = fields.Many2one(
        'gate.review',
        string="Gate",
        ondelete='cascade'
    )

    point_id = fields.Many2one(
        'gate.point.master',
        string="Point",
        required=True
    )

    department_ids = fields.Many2many(
        'hr.department',
        'gate_way_department_rel',
        string='Departments'
    )