# -*- coding: utf-8 -*-
import io
import datetime
from odoo import http
from odoo.http import request, content_disposition


class GanttExportController(http.Controller):

    @http.route('/custom_gantt/export_excel/<int:project_id>',
                type='http', auth='user', methods=['GET'])
    def export_excel(self, project_id, **kwargs):
        try:
            from openpyxl import Workbook
            from openpyxl.styles import (PatternFill, Font, Alignment,
                                          Border, Side, numbers)
            from openpyxl.utils import get_column_letter
        except ImportError:
            return request.make_response(
                "openpyxl not installed. Run: pip install openpyxl",
                headers=[('Content-Type', 'text/plain')]
            )

        project = request.env['gantt.project'].sudo().browse(project_id)
        if not project.exists():
            return request.make_response("Project not found", headers=[('Content-Type','text/plain')])

        tasks = request.env['gantt.task'].sudo().search(
            [('project_id', '=', project_id)],
            order='id asc'
        )

        # ── Date range ────────────────────────────────────────────────
        all_starts = [t.date_start for t in tasks if t.date_start]
        all_stops  = [t.date_stop  for t in tasks if t.date_stop]
        if not all_starts:
            return request.make_response("No tasks with dates found",
                                          headers=[('Content-Type','text/plain')])

        range_start = min(all_starts).date()
        range_end   = max(all_stops).date()
        total_days  = (range_end - range_start).days + 1

        # ── Build WBS tree ────────────────────────────────────────────
        task_map = {t.id: t for t in tasks}
        def get_serial(task, counters={}):
            return ""  # computed below

        rows = []
        root_counter = [0]
        def walk(task, level, parent_serial):
            root_counter[0] += 1 if not parent_serial else 0
            children = [t for t in tasks if t.parent_id and t.parent_id.id == task.id]
            if parent_serial:
                # find my index among siblings
                siblings = [t for t in tasks
                            if t.parent_id and t.parent_id.id == task.parent_id.id]
                idx = siblings.index(task) + 1
                serial = f"{parent_serial}.{idx}"
            else:
                roots = [t for t in tasks if not t.parent_id]
                idx = roots.index(task) + 1
                serial = str(idx)
            rows.append((task, level, serial, bool(children)))
            for child in children:
                walk(child, level + 1, serial)

        roots = [t for t in tasks if not t.parent_id]
        for root in roots:
            walk(root, 0, "")

        # ── Workbook setup ────────────────────────────────────────────
        wb = Workbook()
        ws = wb.active
        ws.title = project.name[:31]

        # Colours
        C_HEADER_BG   = "1A2744"   # dark navy
        C_HEADER_FG   = "FFFFFF"
        C_PHASE_BG    = "2C3E50"   # dark grey for parent rows
        C_PHASE_FG    = "FFFFFF"
        C_ROW_ODD     = "EBF5FB"
        C_ROW_EVEN    = "FFFFFF"
        C_BAR_GREEN   = "2ECC71"   # completed
        C_BAR_RED     = "E74C3C"   # overdue
        C_BAR_BLUE    = "3498DB"   # on track
        C_BAR_PURPLE  = "8E44AD"   # parent bar
        C_WEEKEND     = "F0F0F0"
        C_TODAY       = "E74C3C"
        C_GRID        = "E8E8E8"

        def fill(hex_color):
            return PatternFill("solid", fgColor=hex_color)

        def font(bold=False, color="000000", size=10):
            return Font(bold=bold, color=color, size=size)

        def center():
            return Alignment(horizontal="center", vertical="center", wrap_text=True)

        def left():
            return Alignment(horizontal="left", vertical="center", wrap_text=True)

        thin = Side(style="thin", color="E8E8E8")
        med  = Side(style="medium", color="AAAAAA")
        def border(left_s=thin, right_s=thin, top_s=thin, bottom_s=thin):
            return Border(left=left_s, right=right_s, top=top_s, bottom=bottom_s)

        today = datetime.date.today()

        # ── Fixed columns ─────────────────────────────────────────────
        FIXED_COLS = [
            ("Sr.\nNo.",      5),
            ("Task Name",    30),
            ("Assigned\nTo", 12),
            ("Support\nFn.", 12),
            ("Progress\n(%)",10),
            ("Start",        11),
            ("End",          11),
            ("Days",          6),
            ("Remarks",      20),
        ]
        N_FIXED = len(FIXED_COLS)

        # ── Row 1: Project header ─────────────────────────────────────
        ws.row_dimensions[1].height = 22
        ws.merge_cells(start_row=1, start_column=1,
                       end_row=1, end_column=N_FIXED + total_days)
        c = ws.cell(1, 1,
            value=f"PROJECT: {project.name}   |   Customer: {project.partner_id.name if project.partner_id else ''}   |   Lead: {project.user_id.name if project.user_id else ''}   |   Start: {range_start.strftime('%d %b %Y')}   |   End: {range_end.strftime('%d %b %Y')}")
        c.fill      = fill(C_HEADER_BG)
        c.font      = font(bold=True, color=C_HEADER_FG, size=11)
        c.alignment = center()

        # ── Row 2: Day-of-week header ─────────────────────────────────
        ws.row_dimensions[2].height = 22
        DOW = ["M","T","W","T","F","S","S"]
        for fi, (label, width) in enumerate(FIXED_COLS):
            col = fi + 1
            ws.column_dimensions[get_column_letter(col)].width = width
            c = ws.cell(2, col, value=label)
            c.fill = fill(C_HEADER_BG); c.font = font(bold=True, color=C_HEADER_FG, size=9)
            c.alignment = center(); c.border = border()

        for d in range(total_days):
            day_date = range_start + datetime.timedelta(days=d)
            col = N_FIXED + d + 1
            dow = DOW[day_date.weekday()]
            ws.column_dimensions[get_column_letter(col)].width = 2.2
            is_today = (day_date == today)
            is_wknd  = day_date.weekday() >= 5
            c = ws.cell(2, col, value=dow)
            c.fill      = fill(C_TODAY if is_today else ("D5D8DC" if is_wknd else C_HEADER_BG))
            c.font      = font(bold=True, color=C_HEADER_FG, size=7)
            c.alignment = center()
            c.border    = border()

        # ── Row 3: Day-number header ──────────────────────────────────
        ws.row_dimensions[3].height = 18
        for fi, (label, _) in enumerate(FIXED_COLS):
            c = ws.cell(3, fi+1, value="")
            c.fill = fill(C_HEADER_BG); c.border = border()

        for d in range(total_days):
            day_date = range_start + datetime.timedelta(days=d)
            col = N_FIXED + d + 1
            is_today = (day_date == today)
            is_wknd  = day_date.weekday() >= 5
            c = ws.cell(3, col, value=day_date.day)
            c.fill      = fill(C_TODAY if is_today else ("D5D8DC" if is_wknd else "2C3E50"))
            c.font      = font(bold=is_today, color=C_HEADER_FG, size=7)
            c.alignment = center()
            c.border    = border()

        # ── Row 4 onward: month label merged cells ────────────────────
        # Build month groups
        month_groups = []
        cur_month = None
        cur_start_d = 0
        for d in range(total_days):
            day_date = range_start + datetime.timedelta(days=d)
            key = (day_date.year, day_date.month)
            if key != cur_month:
                if cur_month:
                    month_groups.append((cur_month, cur_start_d, d-1))
                cur_month = key
                cur_start_d = d
        month_groups.append((cur_month, cur_start_d, total_days-1))

        ws.row_dimensions[4].height = 18
        for fi in range(N_FIXED):
            c = ws.cell(4, fi+1, value="")
            c.fill = fill(C_HEADER_BG); c.border = border()

        for (yr, mo), dstart, dend in month_groups:
            col_start = N_FIXED + dstart + 1
            col_end   = N_FIXED + dend   + 1
            if col_end > col_start:
                ws.merge_cells(start_row=4, start_column=col_start,
                               end_row=4,   end_column=col_end)
            label = datetime.date(yr, mo, 1).strftime("%b %Y")
            c = ws.cell(4, col_start, value=label)
            c.fill      = fill("1F618D")
            c.font      = font(bold=True, color=C_HEADER_FG, size=8)
            c.alignment = center()
            c.border    = border(left_s=med, right_s=med)
            # fill rest of month cells
            for d in range(dstart, dend+1):
                col = N_FIXED + d + 1
                cc = ws.cell(4, col)
                cc.fill = fill("1F618D")
                cc.border = border()

        # ── Data rows ─────────────────────────────────────────────────
        DATA_ROW_START = 5
        for ri, (task, level, serial, is_parent) in enumerate(rows):
            row_num = DATA_ROW_START + ri
            ws.row_dimensions[row_num].height = 28

            # Background
            if is_parent:
                bg = C_PHASE_BG
                fg = C_PHASE_FG
            else:
                bg = C_ROW_ODD if ri % 2 == 0 else C_ROW_EVEN
                fg = "2C3E50"

            # Progress & overdue
            prog = task.progress or 0
            is_overdue = (task.date_stop and
                          task.date_stop.date() < today and prog < 100)

            # Fixed columns
            values = [
                serial,
                "  " * level + (task.name or ""),
                task.user_id.name if task.user_id else "",
                "",   # support function
                f"{prog:.0f}%",
                task.date_start.strftime("%d %b %Y") if task.date_start else "",
                task.date_stop.strftime("%d %b %Y")  if task.date_stop  else "",
                f"{(task.date_stop - task.date_start).days}" if task.date_start and task.date_stop else "",
                "",   # remarks
            ]

            for ci, val in enumerate(values):
                col = ci + 1
                c = ws.cell(row_num, col, value=val)
                c.fill = fill(bg)
                c.font = font(bold=is_parent, color=fg, size=9)
                c.alignment = left() if ci == 1 else center()
                c.border = border()

            # Gantt bar columns
            t_start = task.date_start.date() if task.date_start else None
            t_end   = task.date_stop.date()  if task.date_stop  else None

            if prog == 100:
                bar_color = C_BAR_GREEN
            elif is_overdue:
                bar_color = C_BAR_RED
            elif is_parent:
                bar_color = C_BAR_PURPLE
            else:
                bar_color = C_BAR_BLUE

            for d in range(total_days):
                day_date = range_start + datetime.timedelta(days=d)
                col = N_FIXED + d + 1
                c = ws.cell(row_num, col)
                is_wknd = day_date.weekday() >= 5

                if t_start and t_end and t_start <= day_date <= t_end:
                    c.fill = fill(bar_color)
                    # No border on bar cells — avoids black box appearance
                else:
                    gantt_bg = "D5D8DC" if is_parent else (C_WEEKEND if is_wknd else bg)
                    c.fill = fill(gantt_bg)

        # ── Freeze panes ──────────────────────────────────────────────
        ws.freeze_panes = ws.cell(DATA_ROW_START, N_FIXED + 1)

        # ── Auto-filter on header ─────────────────────────────────────
        ws.auto_filter.ref = (
            f"A2:{get_column_letter(N_FIXED)}{DATA_ROW_START + len(rows) - 1}"
        )

        # ── Save ──────────────────────────────────────────────────────
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        filename = f"{project.name}_Gantt_{today.strftime('%Y-%m-%d')}.xlsx"
        return request.make_response(
            buf.getvalue(),
            headers=[
                ('Content-Type',
                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', content_disposition(filename)),
            ]
        )