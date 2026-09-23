# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DocumentPackageInherit(models.Model):
    _inherit = 'xf.doc.approval.document.package'

    def action_open_flowchart(self):
        """Open the APQP Flow Chart dashboard directly from the document package."""
        self.ensure_one()
        if not self.apqp_timeline_chart_id:
            raise UserError(_("No APQP Timeline Chart is linked to this document package."))
        return self.apqp_timeline_chart_id.action_open_flowchart()