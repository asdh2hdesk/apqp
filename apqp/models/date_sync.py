from odoo import api, models

class DocumentApprovalSync(models.Model):
    _inherit = 'document.approval'

    def write(self, vals):
        # Skip synchronization if triggered by another model
        if self.env.context.get('from_timeline_format') or self.env.context.get('from_format_record'):
            return super(DocumentApprovalSync, self).write(vals)
        
        # Perform the write operation
        res = super(DocumentApprovalSync, self).write(vals)
        
        # Check if date fields are being updated
        date_fields = ['plan_start_date', 'plan_end_date', 'actual_start_date', 'actual_end_date']
        if any(field in vals for field in date_fields):
            for rec in self:
                # Update the format record (e.g., iatf.sign.off.members)
                if rec.formate_id and rec.formate.table:
                    try:
                        format_record = self.env[rec.formate.table].browse(int(rec.formate_id))
                        if format_record.exists():
                            format_record.with_context(from_document_approval=True).write({
                                'plan_start_date': rec.plan_start_date,
                                'plan_end_date': rec.plan_end_date,
                                'actual_start_date': rec.actual_start_date,
                                'actual_end_date': rec.actual_end_date,
                            })
                    except ValueError:
                        # Handle case where formate_id is not a valid integer
                        pass

                # Update related apqp.timeline.format records
                timeline_formats = self.env['apqp.timeline.format'].search([('document_approval_id', '=', rec.id)])
                for timeline_format in timeline_formats:
                    timeline_format.with_context(from_document_approval=True).write({
                        'planned_start_date': rec.plan_start_date,
                        'planned_end_date': rec.plan_end_date,
                        'actual_start_date': rec.actual_start_date,
                        'actual_end_date': rec.actual_end_date,
                    })
        return res

class APQPTimelineFormatSync(models.Model):
    _inherit = 'apqp.timeline.format'

    def _cascade_dates_to_subsequent(self, planned_delta=0, actual_delta=0):
        from datetime import timedelta
        if not planned_delta and not actual_delta:
            return
        subsequent = self.timeline_chart_id.timeline_format_ids.filtered(
            lambda r: r.sequence > self.sequence and not r.display_type
        )
        for line in subsequent:
            upd = {}
            if planned_delta:
                if line.planned_start_date:
                    upd['planned_start_date'] = line.planned_start_date + timedelta(days=planned_delta)
                if line.planned_end_date:
                    upd['planned_end_date'] = line.planned_end_date + timedelta(days=planned_delta)
            if actual_delta:
                if line.actual_start_date:
                    upd['actual_start_date'] = line.actual_start_date + timedelta(days=actual_delta)
                if line.actual_end_date:
                    upd['actual_end_date'] = line.actual_end_date + timedelta(days=actual_delta)
            if upd:
                line.with_context(skip_date_cascade=True).write(upd)

    @api.model
    def create(self, vals):
        if 'document_approval_id' in vals and vals.get('document_approval_id'):
            approval = self.env['document.approval'].browse(vals['document_approval_id'])
            if approval.exists():
                vals.setdefault('planned_start_date', approval.plan_start_date)
                vals.setdefault('planned_end_date', approval.plan_end_date)
                vals.setdefault('actual_start_date', approval.actual_start_date)
                vals.setdefault('actual_end_date', approval.actual_end_date)

        record = super(APQPTimelineFormatSync, self).create(vals)

        # Cascade on CREATE — only for trial rows (parent_activity_id set)
        if not self.env.context.get('skip_date_cascade') and record.parent_activity_id:
            from datetime import date as date_cls
            from odoo.fields import Date

            def to_date(v):
                if not v:
                    return None
                return v if isinstance(v, date_cls) else Date.from_string(v)

            ps = to_date(vals.get('planned_start_date'))
            pe = to_date(vals.get('planned_end_date'))
            planned_delta = (pe - ps).days if ps and pe else 0

            as_ = to_date(vals.get('actual_start_date'))
            ae = to_date(vals.get('actual_end_date'))
            actual_delta = (ae - as_).days if as_ and ae else 0

            record._cascade_dates_to_subsequent(
                planned_delta=planned_delta,
                actual_delta=actual_delta,
            )

        return record

    def write(self, vals):
        # Skip if triggered internally
        if self.env.context.get('from_document_approval') or self.env.context.get('from_format_record'):
            return super(APQPTimelineFormatSync, self).write(vals)

        planned_fields = {'planned_start_date', 'planned_end_date'}
        actual_fields = {'actual_start_date', 'actual_end_date'}
        has_planned = bool(planned_fields & vals.keys())
        has_actual = bool(actual_fields & vals.keys())

        # Capture OLD end dates BEFORE write (only for trial rows, only if cascade needed)
        old_data = {}
        if not self.env.context.get('skip_date_cascade'):
            for rec in self:
                if rec.parent_activity_id:
                    old_data[rec.id] = {
                        'planned_end': rec.planned_end_date,
                        'planned_start': rec.planned_start_date,  # ADD
                        'actual_end': rec.actual_end_date,
                        'actual_start': rec.actual_start_date,  # ADD
                    }

        res = super(APQPTimelineFormatSync, self).write(vals)

        # Sync to document.approval (existing logic)
        date_fields = ['planned_start_date', 'planned_end_date', 'actual_start_date', 'actual_end_date']
        if any(f in vals for f in date_fields):
            for rec in self:
                if rec.document_approval_id:
                    rec.document_approval_id.with_context(from_timeline_format=True).write({
                        'plan_start_date': rec.planned_start_date,
                        'plan_end_date': rec.planned_end_date,
                        'actual_start_date': rec.actual_start_date,
                        'actual_end_date': rec.actual_end_date,
                    })
                    if rec.document_approval_id.formate_id and rec.document_approval_id.formate.table:
                        try:
                            format_record = self.env[rec.document_approval_id.formate.table].browse(
                                int(rec.document_approval_id.formate_id)
                            )
                            if format_record.exists():
                                format_record.with_context(from_timeline_format=True).write({
                                    'plan_start_date': rec.planned_start_date,
                                    'plan_end_date': rec.planned_end_date,
                                    'actual_start_date': rec.actual_start_date,
                                    'actual_end_date': rec.actual_end_date,
                                })
                        except ValueError:
                            pass

        # Cascade date shift to subsequent rows
        for rec in self:
            if rec.id not in old_data:
                continue
            old = old_data[rec.id]
            planned_delta = 0
            actual_delta = 0

            if has_planned:
                if old['planned_end'] and rec.planned_end_date:
                    # End date moved — shift by the difference
                    planned_delta = (rec.planned_end_date - old['planned_end']).days
                elif not old['planned_end'] and rec.planned_end_date and rec.planned_start_date:
                    # First time setting dates — shift by full trial duration
                    planned_delta = (rec.planned_end_date - rec.planned_start_date).days

            if has_actual:
                if old['actual_end'] and rec.actual_end_date:
                    actual_delta = (rec.actual_end_date - old['actual_end']).days
                elif not old['actual_end'] and rec.actual_end_date and rec.actual_start_date:
                    actual_delta = (rec.actual_end_date - rec.actual_start_date).days

            rec._cascade_dates_to_subsequent(
                planned_delta=planned_delta,
                actual_delta=actual_delta,
            )

        return res


class IATFSignOffMembers(models.AbstractModel):
    _inherit = 'iatf.sign.off.members'

    def write(self, vals):
        # Skip synchronization if triggered by another model
        if self.env.context.get('from_document_approval') or self.env.context.get('from_timeline_format'):
            return super(IATFSignOffMembers, self).write(vals)
        
        # Perform the write operation
        res = super(IATFSignOffMembers, self).write(vals)
        
        # Check if date fields are being updated
        date_fields = ['plan_start_date', 'plan_end_date', 'actual_start_date', 'actual_end_date']
        if any(field in vals for field in date_fields):
            for rec in self:
                # Find related document.approval records
                approvals = self.env['document.approval'].search([
                    ('formate_id', '=', str(rec.id)),
                    ('formate.table', '=', rec._name)
                ])
                for approval in approvals:
                    # Update document.approval
                    approval.with_context(from_format_record=True).write({
                        'plan_start_date': rec.plan_start_date,
                        'plan_end_date': rec.plan_end_date,
                        'actual_start_date': rec.actual_start_date,
                        'actual_end_date': rec.actual_end_date,
                    })
                    
                    # Update related apqp.timeline.format records
                    timeline_formats = self.env['apqp.timeline.format'].search([('document_approval_id', '=', approval.id)])
                    for timeline_format in timeline_formats:
                        timeline_format.with_context(from_format_record=True).write({
                            'planned_start_date': rec.plan_start_date,
                            'planned_end_date': rec.plan_end_date,
                            'actual_start_date': rec.actual_start_date,
                            'actual_end_date': rec.actual_end_date,
                        })
        return res