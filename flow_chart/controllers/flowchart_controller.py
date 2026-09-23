# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
from datetime import timedelta


# ── IATF keyword detection ─────────────────────────────────────────────────────
IATF_KEYWORDS = {
    'process.flow':                     ['process flow diagram', 'process flow', 'pfd'],
    'asd.pfmea':                        ['pfmea'],
    'control.plan':                     ['control plan'],
    'risk.assessment':                  ['risk assessment', 'risk'],
    'nri.sheet':                        ['nri sheet', 'nri'],
    'lesson.learn':                     ['lesson learn', 'lessons learned'],
    'things.wrong.right':               ['things gone right', 'things wrong', 'tgr', 'tgw'],
    'quary.list':                       ['query list', 'quary list'],
    'pso.checklist':                    ['pso', 'process sign off', 'process sign-off',
                                         'sign off checklist', 'process sign-off checklist'],
    'qc.card':                          ['qc card', 'inspection card'],
    'poka.yoka':                        ['poka yoke', 'poka yoka', 'mistake proof', 'poka-yoke'],
    'customer.specification':           ['customer specification', 'customer spec','customer requirement', 'rfq',
                                         'customer requirement / rfq','customer requirement/rfq'],
    'customer.specific.check':          ['customer spec check', 'cscl'],
    'dimensional.feasibility.sheet':    ['dimensional feasibility', 'feasibility sheet'],
    'key.character.history':            ['key character', 'key characteristic history'],
    'document.control':                 ['part creation', 'customer part creation'],
    'special.characteristics.matrix':   ['special characteristics', 'special characteristic'],
    'supplier':                         ['supplier'],
    'feasibility.commitment':           ['team feasibility', 'feasibility commitment'],
    'team.formation':                   ['team formation'],
    'msa.cpk.plan':                     ['msa', 'cpk', 'msa plan', 'cpk plan', 'capability study', 'process capability',
                                         'msa cpk', 'msa & cpk', 'msa and cpk','preparation of process capability'],
    'gauge.trackingsheet':              ['gauge tracking', 'gauge track', 'gauge sheet',
                                         'gauge tracking sheet'],
    'tools.trackingsheet':              ['tool tracking', 'tools tracking', 'tool track',
                                         'tool sheet', 'tools tracking sheet'],
    'equipment.trackingsheet':          ['equipment tracking', 'equipment track',
                                         'equipment sheet', 'equipment tracking sheet'],
    'customer.satisfaction.evaluation': ['customer satisfaction', 'satisfaction evaluation',
                                         'customer satifaction', 'csat'],
    # ── Quality ─────────────────────────────────────
    'in.process.inspection.report':     ['in process inspection', 'inprocess inspection',
                                         'in-process inspection', 'in process insp'],
    'pre.dispatch.inspection.report':   ['pre dispatch inspection', 'predispatch inspection',
                                         'pre-dispatch inspection', 'pre dispatch',
                                         'predispatch','Pre Dispatch IR','Inspection PreDispatch'],
    'first.part.inspection.report': ['first part inspection', 'first part', 'fpi'],
    'in.coming.inspection.report': ['in coming inspection','incoming inspection',
                                    'incoming ir','report of incoming inspection','incoming'],
}

def _get_iatf_type(name):
    name_lower = (name or '').lower().strip()
    for model, keywords in IATF_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return model
    return ''


class APQPFlowchartController(http.Controller):

    @http.route('/apqp/flowchart_data/<int:chart_id>', type='json', auth='user')
    def get_flowchart_data(self, chart_id, **kwargs):
        chart = request.env['apqp.timeline.chart'].browse(chart_id)
        if not chart.exists():
            return {'error': 'Record not found'}

        today = fields.Date.today()
        phases = request.env['apqp.phase'].search([], order='sequence')

        # ── Build timeframe map ONCE before all loops ─────────────────────────
        timeframe_map = {}
        if chart.document_package_id:
            for tf in chart.document_package_id.phase_timeframe_ids:
                timeframe_map[tf.phase_id.id] = tf

        # ── NEW: Build a lookup map from format name → document.approval record ──
        # Key: lowercased format name, Value: document.approval record
        # This lets us find the document.approval linked to each timeline format
        approval_map = {}
        if chart.document_package_id:
            for approval in chart.document_package_id.document_approval_ids:
                if approval.formate and approval.formate.name:
                    key = approval.formate.name.lower().strip()
                    approval_map[key] = approval
                # Also index by approval.name if set
                if approval.name:
                    key2 = approval.name.lower().strip()
                    if key2 not in approval_map:
                        approval_map[key2] = approval

        attachments_by_phase = {}

        # ── Loop 1: real attachment records ───────────────────────────────────
        for att in chart.attachment_ids:
            pid = att.phase_id.id
            if pid not in attachments_by_phase:
                attachments_by_phase[pid] = []
            attachments_by_phase[pid].append({
                'id':                    att.id,
                'chart_id':              chart.id,
                'source':                'attachment',
                'iatf_type':             _get_iatf_type(att.format_name),
                'format_name':           att.format_name or '',
                'activity':              att.activity or '',
                'document_type':         att.document_type or '',
                'state':                 att.state or 'not_started',
                'planned_start_date':    str(att.planned_start_date) if att.planned_start_date else '',
                'planned_end_date':      str(att.planned_end_date) if att.planned_end_date else '',
                'actual_start_date':     str(att.actual_start_date) if att.actual_start_date else '',
                'actual_end_date':       str(att.actual_end_date) if att.actual_end_date else '',
                'attachment_count':      att.attachment_count,
                'prepared_by':           att.prepared_by.name if att.prepared_by else '',
                'approved_by':           att.approved_by.name if att.approved_by else '',
                'is_confirmed':          att.is_confirmed,
                # attachments don't go through document.approval flow
                'document_approval_id':  False,
                'formate_id':            False,
            })

        # ── Loop 2: format-only records ───────────────────────────────────────
        for fmt in chart.timeline_format_ids:
            if fmt.display_type or fmt.source_attachment_id:
                continue
            pid = fmt.phase_id.id if fmt.phase_id else None
            if not pid:
                continue
            if pid not in attachments_by_phase:
                attachments_by_phase[pid] = []

            # ── NEW: find the matching document.approval for this format ──────
            # Try matching by format name (lowercased)
            fmt_name_lower = (fmt.name or '').lower().strip()
            matched_approval = approval_map.get(fmt_name_lower)

            # If no exact match, try IATF keyword match against approval format names
            if not matched_approval and chart.document_package_id:
                iatf_type = _get_iatf_type(fmt.name)
                if iatf_type:
                    for approval in chart.document_package_id.document_approval_ids:
                        if approval.formate and approval.formate.table == iatf_type:
                            matched_approval = approval
                            break

            doc_approval_id = matched_approval.id if matched_approval else False
            formate_id_val  = matched_approval.formate_id if matched_approval else False
            # formate_id is stored as Char, treat empty string as falsy
            if formate_id_val == '' or formate_id_val == '0':
                formate_id_val = False

            attachments_by_phase[pid].append({
                'id':                    fmt.id,
                'chart_id':              chart.id,
                'source':                'format',
                'iatf_type':             _get_iatf_type(fmt.name),
                'format_name':           fmt.name or '',
                'activity':              fmt.activity or '',
                'document_type':         fmt.document_type or '',
                'state':                 fmt.status or 'not_started',
                'planned_start_date':    str(fmt.planned_start_date) if fmt.planned_start_date else '',
                'planned_end_date':      str(fmt.planned_end_date) if fmt.planned_end_date else '',
                'actual_start_date':     str(fmt.actual_start_date) if fmt.actual_start_date else '',
                'actual_end_date':       str(fmt.actual_end_date) if fmt.actual_end_date else '',
                'attachment_count':      fmt.attachment_count,
                'prepared_by':           '',
                'approved_by':           '',
                'is_confirmed':          False,
                # ── NEW fields for auto-create flow ──────────────────────────
                'document_approval_id':  doc_approval_id,
                'formate_id':            formate_id_val,
                'is_gate_review': fmt.is_gate_review,
            })

        phase_data = []
        for phase in phases:
            pid = phase.id
            docs = attachments_by_phase.get(pid, [])
            total = len(docs)
            if total == 0:
                continue

            state_counts = {}
            for doc in docs:
                s = doc['state']
                state_counts[s] = state_counts.get(s, 0) + 1

            completed   = state_counts.get('completed', 0)
            in_progress = state_counts.get('in_progress', 0)
            not_started = state_counts.get('not_started', 0)
            delayed     = state_counts.get('delayed', 0)
            phase_progress = round((completed / total) * 100) if total > 0 else 0

            # ── Get planned dates from timeframe (not from apqp.phase) ────────
            tf = timeframe_map.get(pid)
            planned_start = str(tf.planned_start_date) if tf and tf.planned_start_date else ''
            planned_end   = str(tf.planned_end_date)   if tf and tf.planned_end_date   else ''

            phase_data.append({
                'id':            pid,
                'name':          phase.name,
                'sequence':      phase.sequence,
                'color':         phase.color,
                'total_docs':    total,
                'progress':      phase_progress,
                'planned_start': planned_start,
                'planned_end':   planned_end,
                'state_counts':  {
                    'completed':   completed,
                    'in_progress': in_progress,
                    'not_started': not_started,
                    'delayed':     delayed,
                },
                'documents': docs,
            })

        all_docs = chart.attachment_ids

        # ── PPAP Summary ──────────────────────────────────────────────────────
        ppap_phase = phases.filtered(
            lambda p: 'validation' in p.name.lower() or '4' in p.name
        )
        ppap_phase = ppap_phase[0] if ppap_phase else None

        ppap_docs = chart.attachment_ids.filtered(
            lambda d: d.phase_id.id == ppap_phase.id
        ) if ppap_phase else chart.env['apqp.timeline.attachment'].browse()

        ppap_total     = len(ppap_docs)
        ppap_completed = len(ppap_docs.filtered(lambda d: d.state == 'completed'))
        ppap_in_prog   = len(ppap_docs.filtered(lambda d: d.state == 'in_progress'))
        ppap_not_start = len(ppap_docs.filtered(lambda d: d.state == 'not_started'))
        ppap_delayed   = len(ppap_docs.filtered(lambda d: d.state == 'delayed'))
        ppap_approved  = len(ppap_docs.filtered(lambda d: d.approved_by))
        ppap_progress  = round((ppap_completed / ppap_total) * 100) if ppap_total > 0 else 0
        ppap_ready     = ppap_total > 0 and ppap_completed == ppap_total and ppap_approved == ppap_total

        ppap_doc_list = [{
            'name':     d.format_name or '',
            'state':    d.state or 'not_started',
            'due': d.planned_end_date.strftime('%d/%m/%y') if d.planned_end_date else '',
            'approved': bool(d.approved_by),
        } for d in ppap_docs.sorted('sequence')][:8]

        ppap_summary = {
            'phase_name':  ppap_phase.name if ppap_phase else 'Product & Process Validation',
            'total':       ppap_total,
            'completed':   ppap_completed,
            'in_progress': ppap_in_prog,
            'not_started': ppap_not_start,
            'delayed':     ppap_delayed,
            'approved':    ppap_approved,
            'progress':    ppap_progress,
            'ready':       ppap_ready,
            'docs':        ppap_doc_list,
        }

        # ── Attention Needed ──────────────────────────────────────────────────
        attention_items = []

        delayed_docs = all_docs.filtered(lambda d: d.state == 'delayed')
        if delayed_docs:
            attention_items.append({
                'type':    'error',
                'message': f'{len(delayed_docs)} document(s) are delayed past due date',
                'docs': [{
                    'name':  d.format_name or '',
                    'phase': d.phase_id.name if d.phase_id else '',
                    'due': d.planned_end_date.strftime('%d/%m/%y') if d.planned_end_date else '',
                } for d in delayed_docs],
            })

        soon = today + timedelta(days=7)
        due_soon = all_docs.filtered(
            lambda d: d.planned_end_date
            and today <= d.planned_end_date <= soon
            and d.state not in ('completed',)
        )
        if due_soon:
            attention_items.append({
                'type':    'warning',
                'message': f'{len(due_soon)} document(s) due within next 7 days',
            })

        pending_approval = all_docs.filtered(
            lambda d: d.document_type == 'attachment'
            and d.prepared_by
            and not d.approved_by
            and d.state == 'in_progress'
        )
        if pending_approval:
            attention_items.append({
                'type':    'info',
                'message': f'{len(pending_approval)} document(s) pending approval',
                'docs': [{
                    'name':        d.format_name or '',
                    'phase':       d.phase_id.name if d.phase_id else '',
                    'due':         d.planned_end_date.strftime('%d/%m/%y') if d.planned_end_date else '',
                    'prepared_by': d.prepared_by.name if d.prepared_by else '',
                    'reviewed_by': d.reviewed_by.name if d.reviewed_by else '',
                    'approver_dept': ', '.join(d.department_ids.mapped('name')) if d.department_ids else 'Not Assigned',
                } for d in pending_approval],
            })

        overdue_start = all_docs.filtered(
            lambda d: d.state == 'not_started'
            and d.planned_start_date
            and today > d.planned_start_date
        )
        if overdue_start:
            attention_items.append({
                'type':    'muted',
                'message': f'{len(overdue_start)} document(s) not started (past planned start)',
            })

        if ppap_delayed > 0:
            attention_items.append({
                'type':    'error',
                'message': f'PPAP: {ppap_delayed} validation document(s) delayed',
            })

        if not ppap_ready and ppap_total > 0:
            attention_items.append({
                'type':    'warning',
                'message': f'PPAP submission not ready — {ppap_total - ppap_completed} doc(s) pending',
            })

        if not attention_items:
            attention_items.append({
                'type':    'info',
                'message': 'No attention items — project on track!',
            })

        # ── Critical Path ─────────────────────────────────────────────────────
        total_docs = len(all_docs)

        completed_count      = len(all_docs.filtered(lambda d: d.state == 'completed'))
        doc_completion       = round((completed_count / total_docs) * 100) if total_docs else 0

        attachment_type_docs = all_docs.filtered(lambda d: d.document_type == 'attachment')
        approved_count       = len(attachment_type_docs.filtered(lambda d: d.approved_by))
        approval_readiness   = round((approved_count / len(attachment_type_docs)) * 100) if attachment_type_docs else 0

        non_delayed          = len(all_docs.filtered(lambda d: d.state != 'delayed'))
        dependency_clearance = round((non_delayed / total_docs) * 100) if total_docs else 0

        reviewed_docs        = all_docs.filtered(lambda d: d.prepared_by and d.reviewed_by)
        revision_clearance   = round((len(reviewed_docs) / total_docs) * 100) if total_docs else 0

        critical_path = [
            {'label': 'Documents Completion', 'value': doc_completion,       'color': '#7c3aed'},
            {'label': 'Approval Readiness',   'value': approval_readiness,   'color': '#0d9488'},
            {'label': 'Dependency Clearance', 'value': dependency_clearance, 'color': '#d97706'},
            {'label': 'Revision Clearance',   'value': revision_clearance,   'color': '#db2777'},
        ]

        phase_ready = (
            all(p['progress'] == 100 for p in phase_data)
            and len(delayed_docs) == 0
        )

        doc_type_labels = {
            'safelaunch': 'Safe Launch',
            'prototype':  'Prototype',
            'prelaunch':  'PreLaunch',
            'production': 'Production',
        }

        return {
            'chart_id':         chart.id,
            'project_name':     chart.project_name or '',
            'customer':         chart.partner_id.name if chart.partner_id else '',
            'doc_type':         doc_type_labels.get(chart.doc_type, chart.doc_type or ''),
            'launch_type':      doc_type_labels.get(chart.doc_type, chart.doc_type or ''),
            'overall_progress': round(chart.progress),
            'state':            chart.state,
            'start_date':       str(chart.start_date) if chart.start_date else '',
            'target_date':      str(chart.target_date) if chart.target_date else '',
            'planned_start':    str(chart.start_date) if chart.start_date else '',
            'planned_end':      str(chart.target_date) if chart.target_date else '',
            'champion':         (chart.gantt_mom_id.champion_id.name
                                 if chart.gantt_mom_id and chart.gantt_mom_id.champion_id
                                 else (chart.cft_team[0].name if chart.cft_team else '')),
            'phases':           phase_data,
            'ppap_summary':     ppap_summary,
            'attention_items':  attention_items,
            'critical_path':    critical_path,
            'phase_ready':      phase_ready,
        }