# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class APQPTimelineChartFlowchart(models.Model):
    _inherit = 'apqp.timeline.chart'

    def action_open_flowchart(self):
        """Open the APQP Project Flow Dashboard in full screen."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'apqp_flowchart_dashboard',
            'name': _('APQP Flow Dashboard - %s') % self.project_name,
            'target': 'fullscreen',
            'params': {
                'chart_id': self.id,
            },
        }
    def action_open_gantt(self):
        """Open the Gantt chart view directly (same as clicking Gantt Chart button on project)."""
        self.ensure_one()
        if not self.gantt_project_id:
            self.action_create_sync_gantt()
        return self.gantt_project_id.action_open_gantt()

    def action_open_mom_report(self):
        """Open the MOM form directly (same as MOM button on Gantt project)."""
        self.ensure_one()
        if not self.gantt_project_id:
            self.action_create_sync_gantt()
        return self.gantt_project_id.action_open_mom()

    def action_open_iatf_full_view(self, iatf_type):
        """Open the Full View HTML report for IATF documents."""
        self.ensure_one()
        package = self.document_package_id
        if not package:
            raise UserError(_("No document package linked to this timeline chart."))

        REPORT_MAP = {
            'process.flow': 'iatf_full_view.action_report_process_flow_html',
            'asd.pfmea': 'iatf_full_view.action_report_pfmea_html',
            'control.plan': 'iatf_full_view.action_report_control_plan_html',
            'risk.assessment': 'iatf_full_view.action_report_risk_assessment_html',
            'nri.sheet': 'iatf_full_view.action_report_nri_sheet_html',
            'lesson.learn': 'iatf_full_view.action_report_lesson_learn_html',
            'things.wrong.right': 'iatf_full_view.action_report_things_wrong_right_html',
            'quary.list': 'iatf_full_view.action_report_query_list_html',
            'pso.checklist': 'iatf_full_view.action_report_pso_html',
            'qc.card': 'iatf_full_view.action_report_qc_html',
            'poka.yoka': 'iatf_full_view.action_report_poka_yoke_html',
            'customer.specification': 'iatf_full_view.action_report_customer_specification_html',
            'customer.specific.check': 'iatf_full_view.action_report_customer_spec_check_html',
            'dimensional.feasibility.sheet': 'iatf_full_view.action_report_dimensional_feasibility_html',
            'key.character.history': 'iatf_full_view.action_report_key_character_history_html',
            'document.control': 'iatf_full_view.action_report_customer_part_creation_html',
            'special.characteristics.matrix': 'iatf_full_view.action_report_special_characteristics_matrix_html',
            'supplier': 'iatf_full_view.action_report_supplier_html',
            'feasibility.commitment': 'iatf_full_view.action_report_team_feasibility_html',
            'team.formation': 'iatf_full_view.action_report_team_formation_html',
            'customer.satisfaction.evaluation': 'iatf_full_view.action_report_customer_satisfaction_html',
            'equipment.trackingsheet': 'iatf_full_view.action_report_equipment_tracking_sheet_html',
            'gauge.trackingsheet': 'iatf_full_view.action_report_gauge_tracking_sheet_html',
            'msa.cpk.plan': 'iatf_full_view.action_report_msa_cpk_html',
            'tools.trackingsheet': 'iatf_full_view.action_report_tools_tracking_sheet_html',

            'in.process.inspection.report': 'quality_full_view.action_report_inprocess_inspection_html',
            'pre.dispatch.inspection.report': 'quality_full_view.action_report_predispatch_inspection_html',
            'first.part.inspection.report': 'quality_full_view.action_report_firstpart_inspection_html',
            'in.coming.inspection.report': 'quality_full_view.action_report_incoming_inspection_html',
        }

        report_ref = REPORT_MAP.get(iatf_type)
        if not report_ref:
            raise UserError(_("Unknown IATF document type: %s") % iatf_type)

        record = self.env[iatf_type].search(
            [('project_id', '=', package.id)], limit=1
        )
        if not record:
            raise UserError(_("No %s record found for this project.") % iatf_type)

        return self.env.ref(report_ref).report_action(record)