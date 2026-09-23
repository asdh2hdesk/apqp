# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime, time
import io
import base64

class APQPTimelineChart(models.Model):
    _inherit = 'apqp.timeline.chart'

    gantt_project_id = fields.Many2one('gantt.project', string='Gantt Project', ondelete='set null')
    gantt_chart_canvas = fields.Char(string='Gantt Chart Canvas')
    gantt_mom_id = fields.Many2one('gantt.mom', string='Gantt MOM', ondelete='set null')
    gantt_mom_ids = fields.One2many('gantt.mom', related='gantt_project_id.mom_ids', string='Gantt MOMs',
                                    readonly=False)

    def action_create_sync_gantt(self):
        """Create or update the linked Gantt project and synchronize all tasks."""
        self.ensure_one()
        
        # Ensure timeline structure and attachments are synced before Gantt sync
        self._ensure_timeline_structure()
        self._sync_all_attachments()
        
        GanttProject = self.env['gantt.project']
        GanttTask = self.env['gantt.task']

        # 1. Create or Find Gantt Project
        if not self.gantt_project_id:
            project_vals = {
                'name': self.project_name,
                'partner_id': self.partner_id.id,
                'date_start': self.project_start_date or self.start_date,
                'date_end': self.project_end_date or self.target_date,
                'cft_team_ids': [(6, 0, self.cft_team.ids)],
                'apqp_timeline_chart_id': self.id,
            }
            project = GanttProject.create(project_vals)
            self.gantt_project_id = project.id
        else:
            project = self.gantt_project_id
            project.write({
                'name': self.project_name,
                'partner_id': self.partner_id.id,
                'cft_team_ids': [(6, 0, self.cft_team.ids)],
                'apqp_timeline_chart_id': self.id,
            })

        # 1.5. Ensure Single MOM Record
        if not self.gantt_mom_id:
            # Check if project already has a MOM
            if project.mom_ids:
                self.gantt_mom_id = project.mom_ids[0].id
            else:
                mom_vals = {
                    'project_id': project.id,
                    'subject': f"{self.project_name} - Project MOM",
                    'champion_id': self.env.user.id,
                }
                mom = self.env['gantt.mom'].create(mom_vals)
                self.gantt_mom_id = mom.id

        # 2. Sync Timeline Formats to Gantt Tasks
        current_parent = False
        for line in self.timeline_format_ids.sorted('sequence'):
            if line.display_type == 'line_section':
                # Create/Update Parent Task (Phase)
                task_vals = self._prepare_gantt_task_vals(line, project)
                if not line.gantt_task_id:
                    task = GanttTask.create(task_vals)
                    line.gantt_task_id = task.id
                else:
                    line.gantt_task_id.write(task_vals)
                current_parent = line.gantt_task_id
            elif not line.display_type:
                # Create/Update Child Task
                task_vals = self._prepare_gantt_task_vals(line, project, parent=current_parent)
                if not line.gantt_task_id:
                    task = GanttTask.create(task_vals)
                    line.gantt_task_id = task.id
                else:
                    line.gantt_task_id.write(task_vals)
            # Notes are ignored for now as Gantt tasks

        # Clean up any legacy duplicate phase roots for this project so the
        # Gantt view / exports never show a phase twice after syncing.
        GanttTask.archive_duplicate_phase_roots(project_id=project.id)

        return True

    def _prepare_gantt_task_vals(self, line, project, parent=False):
        """Prepare values for a gantt.task record from an apqp.timeline.format line."""
        
        # Datetime conversions
        def to_dt(d, t=time.min):
            if not d: return False
            return datetime.combine(d, t)

        vals = {
            'name': line.name,
            'project_id': project.id,
            'parent_id': parent.id if parent else False,
            'apqp_timeline_format_id': line.id,
            'remark': line.reference or '',
            'is_gate_review': line.is_gate_review,
            'gate_review_id': line.gate_review_id.id,
        }
        
        # Planned dates - Ensure date_stop is always set if date_start is set (mandatory field)
        if line.planned_start_date:
            vals['date_start'] = to_dt(line.planned_start_date, time.min)
            if line.planned_end_date:
                vals['date_stop'] = to_dt(line.planned_end_date, time.max)
            else:
                vals['date_stop'] = to_dt(line.planned_start_date, time.max)
        elif line.planned_end_date:
             vals['date_stop'] = to_dt(line.planned_end_date, time.max)
             vals['date_start'] = to_dt(line.planned_end_date, time.min)
        else:
            # Fallback to today if no dates are set but record is being created
            today = fields.Date.today()
            vals['date_start'] = to_dt(today, time.min)
            vals['date_stop'] = to_dt(today, time.max)
        
        # Actual dates
        if line.actual_start_date:
            vals['actual_date_start'] = to_dt(line.actual_start_date, time.min)
        if line.actual_end_date:
            vals['actual_date_stop'] = to_dt(line.actual_end_date, time.max)

        # Status mapping if needed (optional)
        # Progress sync
        if line.status == 'completed':
            vals['progress'] = 100.0
        
        return vals

    def action_open_gantt_view(self):
        self.ensure_one()
        if not self.gantt_project_id:
            self.action_create_sync_gantt()
        return self.gantt_project_id.action_open_gantt()

    # ── MOM EXCEL REPORT ───────────────────────────────────────────

    def action_print_mom_report(self):

        self.ensure_one()

        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        except ImportError:
            raise Exception("openpyxl is required. Install it with: pip install openpyxl")

        # ── Gather data ──────────────────────────────────────────
        cft_names = ', '.join(self.cft_team.mapped('name')) if self.cft_team else ''
        champion_name = ''
        if self.gantt_mom_id and self.gantt_mom_id.champion_id:
            champion_name = self.gantt_mom_id.champion_id.name
        elif self.gantt_project_id and self.gantt_project_id.cft_team_ids:
            champion_name = self.gantt_project_id.cft_team_ids[0].name

        # Collect MOM lines from all MOMs under this project
        mom_lines = self.env['gantt.mom.line']
        if self.gantt_project_id:
            moms = self.env['gantt.mom'].search([('project_id', '=', self.gantt_project_id.id)])
            mom_lines = self.env['gantt.mom.line'].search([('mom_id', 'in', moms.ids)])
        elif self.gantt_mom_id:
            mom_lines = self.gantt_mom_id.line_ids

        status_map = {
            'open': 'Open',
            'in_progress': 'In Progress',
            'done': 'Done',
            'cancelled': 'Cancelled',
        }


        import re as _re
        def _strip_html(html):
            if not html:
                return ''
            return _re.sub(r'<[^>]+>', '', html).strip()

        lines_data = []
        for idx, line in enumerate(mom_lines, start=1):
            dps = line.discussion_point_ids.sorted(key=lambda p: (p.sequence, p.id))
            dp_rows = []
            for dp in dps:
                dp_rows.append({
                    'points': dp.name or '',
                    'points_raised_by': dp.raised_by_id.name if dp.raised_by_id else '',
                    'responsibility': dp.responsibility_id.name if dp.responsibility_id else '',
                    'dp_status': dp.status.replace('_', ' ').title() if dp.status else '',
                })
            if not dp_rows:
                dp_rows = [{'points': '', 'points_raised_by': '', 'responsibility': '', 'dp_status': ''}]

            lines_data.append({
                'sr_no': idx,
                'agenda': line.agenda or '',
                'start_date': line.start_date.strftime('%d-%m-%Y') if line.start_date else '',
                'completion_date': line.completion_date.strftime('%d-%m-%Y') if line.completion_date else '',
                'phase_task': line.task_id.name if line.task_id else '',
                'remark': line.remark or '',
                'additional_notes': _strip_html(line.mom_id.notes if line.mom_id else ''),
                'dp_rows': dp_rows,
            })

        wb = self._build_mom_excel(
            company_name=self.env.company.name or 'INSPIRON ENGINEERING PRIVATE LIMITED',
            company_logo=self.env.user.company_id.logo,
            date_str=fields.Date.today().strftime('%d-%m-%Y'),
            project_name=self.project_name or '',
            customer_details=self.partner_id.name if self.partner_id else '',
            project_equipment_description=self.part_name or self.project_name or '',
            cft_team=cft_names,
            champion=champion_name,
            lines=lines_data,
        )


        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        file_data = base64.b64encode(output.read()).decode('utf-8')

        filename = f"MOM_Report_{self.project_name or 'Report'}_{fields.Date.today()}.xlsx"

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': file_data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def _build_mom_excel(self, company_name, company_logo, date_str, project_name,
                         customer_details, project_equipment_description,
                         cft_team, champion, lines):
        """Build and return the openpyxl Workbook for the MOM report."""
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import range_boundaries
        from openpyxl.drawing.image import Image as XLImage

        wb = Workbook()
        ws = wb.active
        ws.title = "MOM"


        col_widths = {
            'A': 20,  # SR.NO
            'B': 32,  # AGENDA
            'C': 14,  # START DATE
            'D': 22,  # ACTUAL COMPLETION DATE
            'E': 20,  # PHASE/TASK
            'F': 13,  # STATUS
            'G': 18,  # POINTS
            'H': 22,  # POINTS RAISED BY
            'I': 22,  # RESPONSIBILITY
            'J': 26,  # REMARK
            'K': 28,  # ADDITIONAL NOTES
        }
        for col, width in col_widths.items():
            ws.column_dimensions[col].width = width


        ws.row_dimensions[1].height = 18
        ws.row_dimensions[2].height = 22
        ws.row_dimensions[3].height = 35
        ws.row_dimensions[4].height = 35
        ws.row_dimensions[5].height = 22
        ws.row_dimensions[6].height = 40
        ws.row_dimensions[7].height = 20
        ws.row_dimensions[8].height = 30


        def side(style='thin'):
            return Side(style=style, color='000000')

        thick_b = Border(left=side('medium'), right=side('medium'),
                         top=side('medium'), bottom=side('medium'))
        thin_b = Border(left=side('thin'), right=side('thin'),
                        top=side('thin'), bottom=side('thin'))

        orange_fill = PatternFill('solid', start_color='F4A229', end_color='F4A229')
        dark_fill = PatternFill('solid', start_color='1F3864', end_color='1F3864')
        lblue_fill = PatternFill('solid', start_color='D9E1F2', end_color='D9E1F2')

        f_bold = Font(name='Arial', bold=True, size=11)
        f_bold_white = Font(name='Arial', bold=True, size=11, color='FFFFFF')
        f_normal = Font(name='Arial', size=10)
        f_title = Font(name='Arial', bold=True, size=14)
        f_hdr = Font(name='Arial', bold=True, size=10)

        center_v = Alignment(horizontal='center', vertical='center', wrap_text=True)
        left_v = Alignment(horizontal='left', vertical='center', wrap_text=True)

        def apply_border_range(min_row, min_col, max_row, max_col, border):
            for r in range(min_row, max_row + 1):
                for c in range(min_col, max_col + 1):
                    ws.cell(r, c).border = border

        def merge_set(cell_range, value, font=None, fill=None, align=None, border=None):
            ws.merge_cells(cell_range)
            start_cell = ws[cell_range.split(':')[0]]
            if value is not None:
                start_cell.value = value
            if font:   start_cell.font = font
            if fill:   start_cell.fill = fill
            if align:  start_cell.alignment = align
            if border:
                min_col, min_row, max_col, max_row = range_boundaries(cell_range)
                apply_border_range(min_row, min_col, max_row, max_col, border)

        def set_cell(cell, value, font=None, fill=None, align=None, border=None):
            cell.value = value
            if font:   cell.font = font
            if fill:   cell.fill = fill
            if align:  cell.alignment = align
            if border: cell.border = border

        # ── ROW 1: MOM label ─────────────────────────────────────────
        set_cell(ws['A1'], 'MOM', font=f_bold)

        # ── Header block now spans A–K (11 cols) ─────────────────────
        # Logo: A2:A4
        merge_set('A2:A4', None, border=thick_b)

        # Company name: B2:H4  (wider now — covers middle columns)
        merge_set('B2:H4', company_name, font=f_title, align=center_v, border=thick_b)

        # Right-side labels: I2:J_ → use cols I & J for label, K for value
        set_cell(ws['I2'], 'Date:', font=f_bold, fill=lblue_fill, align=left_v, border=thick_b)
        merge_set('J2:K2', date_str, font=f_normal, align=left_v, border=thick_b)

        set_cell(ws['I3'], 'Project Name', font=f_bold, fill=lblue_fill, align=left_v, border=thick_b)
        merge_set('J3:K3', project_name, font=f_normal, align=left_v, border=thick_b)

        set_cell(ws['I4'], 'Location', font=f_bold, fill=lblue_fill, align=left_v, border=thick_b)
        merge_set('J4:K4', '', font=f_normal, align=left_v, border=thick_b)

        # ── ROW 5: Customer Details + Champion ───────────────────────
        set_cell(ws['A5'], 'Customer Details:', font=f_bold, fill=lblue_fill, align=left_v, border=thick_b)
        merge_set('B5:H5', customer_details, font=f_normal, align=left_v, border=thick_b)
        set_cell(ws['I5'], 'Champion', font=f_bold, fill=lblue_fill, align=left_v, border=thick_b)
        merge_set('J5:K5', champion, font=f_normal, align=left_v, border=thick_b)

        # ── ROW 6: Project/Equipment Description + CFT Team ──────────
        set_cell(ws['A6'], 'Project / Equipment\nDescription:',
                 font=f_bold, fill=lblue_fill,
                 align=Alignment(horizontal='left', vertical='center', wrap_text=True),
                 border=thick_b)
        merge_set('B6:H6', project_equipment_description, font=f_normal, align=left_v, border=thick_b)
        set_cell(ws['I6'], 'CFT Team', font=f_bold, fill=lblue_fill, align=left_v, border=thick_b)
        merge_set('J6:K6', cft_team, font=f_normal, align=left_v, border=thick_b)


        try:
            from PIL import Image as PILImage
            import io as _io

            if company_logo:
                img_data = base64.b64decode(company_logo)
                pil_img = PILImage.open(_io.BytesIO(img_data))
                w, h = pil_img.size
                ratio = w / h
                if w > 160: w = 160; h = int(w / ratio)
                if h > 200: h = 200; w = int(h * ratio)
                pil_img = pil_img.resize((w, h), PILImage.LANCZOS)
                buf = _io.BytesIO()
                pil_img.save(buf, format='PNG')
                buf.seek(0)
                xl_img = XLImage(buf)
                xl_img.anchor = 'A2'
                ws.add_image(xl_img)
            else:
                ws['A2'].value = '@ Your logo'
                ws['A2'].font = Font(name='Arial', italic=True, size=10, color='666666')
                ws['A2'].alignment = center_v
        except Exception:
            ws['A2'].value = '@ Your logo'
            ws['A2'].font = Font(name='Arial', italic=True, size=10, color='666666')
            ws['A2'].alignment = center_v

        # ── ROW 7: "MOM Points" dark bar — full width A:K ────────────
        merge_set('A7:K7', 'MOM Points',
                  font=f_bold_white, fill=dark_fill, align=center_v, border=thick_b)


        headers = [
            'SR.NO',  # A col 1
            'AGENDA',  # B col 2
            'START DATE',  # C col 3
            'ACTUAL\nCOMPLETION DATE',  # D col 4
            'PHASE/TASK',  # E col 5  ← swapped
            'STATUS',  # F col 6  ← swapped
            'POINTS',  # G col 7
            'POINTS\nRAISED BY',  # H col 8
            'RESPONSIBILITY',  # I col 9
            'REMARK',  # J col 10
            'ADDITIONAL NOTES',  # K col 11
        ]
        for col_idx, hdr in enumerate(headers, start=1):
            cell = ws.cell(row=8, column=col_idx, value=hdr)
            cell.font = f_hdr
            cell.fill = orange_fill
            cell.alignment = center_v
            cell.border = thick_b



        MERGE_COLS = [1, 2, 3, 4, 5, 10, 11]  # 1-based col indices to merge (E=PHASE/TASK now merged)
        DP_COLS = [6, 7, 8, 9]  # per-dp cols (no merge)

        # -- helper: write + style a single cell -----------------------
        def _write(r, c, val, border=None, fill=None, h_align='left'):
            cell = ws.cell(row=r, column=c, value=val)
            cell.font = f_normal
            cell.alignment = Alignment(
                horizontal=h_align, vertical='center', wrap_text=True)
            cell.border = border or thin_b
            if fill:
                cell.fill = fill

        from openpyxl.styles.borders import Border as _Border, Side as _Side
        def _side(s='thin'):
            return _Side(style=s, color='000000')

        # outer border applied to every cell of merged region individually
        def _outer_border(r, c, row_span, is_first_dp, is_last_dp):
            top = _side('medium') if is_first_dp else _side(None)
            bottom = _side('medium') if is_last_dp else _side(None)
            return _Border(left=_side('thin'), right=_side('thin'),
                           top=top, bottom=bottom)

        current_row = 9
        FIXED_EMPTY = 10  # minimum empty rows at end if fewer groups

        for g in lines:
            dp_rows = g['dp_rows']
            n = len(dp_rows)  # number of Excel rows this group spans

            # -- write merged-column cells (value only in first row) ---
            merged_vals = [
                g['sr_no'],  # col 1  A
                g['agenda'],  # col 2  B
                g['start_date'],  # col 3  C
                g['completion_date'],  # col 4  D
                g['phase_task'],  # col 5  E  (PHASE/TASK — merged)
                '',  # col 6  F  (dp STATUS — handled below)
                '',  # col 7  G  (dp POINTS)
                '',  # col 8  H  (dp RAISED BY)
                '',  # col 9  I  (dp RESPONSIBILITY)
                g['remark'],  # col 10 J
                g['additional_notes'],  # col 11 K
            ]

            for dp_i, dp in enumerate(dp_rows):
                r = current_row + dp_i
                ws.row_dimensions[r].height = 40

                for c in range(1, 12):
                    if c in MERGE_COLS:
                        val = merged_vals[c - 1] if dp_i == 0 else None
                        h = 'center' if c == 1 else 'left'
                        b = _outer_border(r, c, n, dp_i == 0, dp_i == n - 1)
                        _write(r, c, val, border=b, h_align=h)
                    else:
                        # per-dp columns
                        if c == 6:
                            val = dp.get('dp_status', '')
                        elif c == 7:
                            val = dp.get('points', '')
                        elif c == 8:
                            val = dp.get('points_raised_by', '')
                        elif c == 9:
                            val = dp.get('responsibility', '')
                        else:
                            val = ''
                        _write(r, c, val)

            # -- merge cells for the merged columns -------------------
            if n > 1:
                r_start = current_row
                r_end = current_row + n - 1
                for c in MERGE_COLS:
                    from openpyxl.utils import get_column_letter
                    col_ltr = get_column_letter(c)
                    ws.merge_cells(f'{col_ltr}{r_start}:{col_ltr}{r_end}')
                    # Re-apply style on the merged (top-left) cell
                    mc = ws.cell(row=r_start, column=c)
                    mc.alignment = Alignment(
                        horizontal='center' if c == 1 else 'left',
                        vertical='center', wrap_text=True)
                    mc.border = Border(
                        left=_side('thin'), right=_side('thin'),
                        top=_side('medium'), bottom=_side('medium'))

            current_row += n

        # -- fill fixed empty rows if needed --------------------------
        filled = current_row - 9
        for i in range(max(0, FIXED_EMPTY - filled)):
            r = current_row + i
            ws.row_dimensions[r].height = 40
            for c in range(1, 12):
                _write(r, c, '')

        return wb