/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

// ─── Phase icon map ───────────────────────────────────────────────────────────
const PHASE_ICONS = ["📋", "🎯", "📦", "⚙️", "🛡️", "🚀", "🔍", "📊"];

const STATE_LABEL_MAP = {
    completed:   "Completed",
    in_progress: "In Progress",
    not_started: "Not Started",
    delayed:     "Delayed",
};

// ─── Helper: format date string ──────────────────────────────────────────────
function fmtDate(d) {
    if (!d) return "";
    try {
        const dt = new Date(d);
        return dt.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
    } catch {
        return d;
    }
}

// ─── PhaseCard sub-component ─────────────────────────────────────────────────
class PhaseCard extends Component {
    static template = "apqp.FlowchartPhaseCard";
    static props = ["phase", "themeIdx", "onViewDocs"];

    setup() {
        this.state = useState({ expanded: false, loadingDocId: null });
        this.actionService  = useService("action");
        this.notification   = useService("notification");

        this.onDocClick      = this.onDocClick.bind(this);
        this.onToggleExpand  = this.onToggleExpand.bind(this);
        this.onViewDocsClick = this.onViewDocsClick.bind(this);
    }

    get stateRows() {
        const sc = this.props.phase.state_counts || {};
        return Object.entries(STATE_LABEL_MAP)
            .filter(([k]) => (sc[k] || 0) > 0)
            .map(([k, label]) => ({ key: k, label, count: sc[k] || 0 }));
    }

    get visibleDocs() {
        const docs = this.props.phase.documents || [];
        return this.state.expanded ? docs : docs.slice(0, 8);
    }

    get hasMoreDocs() {
        return !this.state.expanded && (this.props.phase.documents || []).length > 8;
    }

    get extraDocsCount() {
        return (this.props.phase.documents || []).length - 8;
    }

    onToggleExpand(ev) {
        ev.stopPropagation();
        this.state.expanded = !this.state.expanded;
    }

    // ─── MAIN DOC CLICK HANDLER ───────────────────────────────────────────────
    async onDocClick(ev, doc) {
        ev.stopPropagation();
        if (!doc || !doc.id) return;

        // Prevent double-clicks while loading
        if (this.state.loadingDocId === doc.id) return;

        // ✅ Push a history entry so the browser Back button returns to THIS
        // dashboard instead of skipping straight to the previous Odoo page
        // (e.g. the Project form). URL reflects WHAT was chosen
        // (e.g. "risk_assessment") instead of a generic numeric id.
        const slugSource = doc.iatf_type || doc.format_name || doc.document_type || `doc-${doc.id}`;
        const slug = slugSource
            .toString()
            .toLowerCase()
            .replace(/\./g, '_')      // risk.assessment -> risk_assessment
            .replace(/[^a-z0-9_]+/g, '_')
            .replace(/^_+|_+$/g, '');
        const baseUrl = window.location.pathname + window.location.search;
        const newUrl  = baseUrl + `#${slug}`;
        window.history.pushState({ apqpDocId: doc.id, apqpSlug: slug }, "", newUrl);

        if (doc.is_gate_review || (doc.activity && doc.activity.toLowerCase().includes('gate review'))) {
            this.state.loadingDocId = doc.id;
            try {
                const action = await rpc("/web/dataset/call_kw", {
                    model:  "apqp.timeline.format",
                    method: "action_open_phase_mom",
                    args:   [[doc.id]],
                    kwargs: {},
                });
                if (action) {
                    return this.actionService.doAction(action);
                } else {
                    this.notification.add(
                        "No MOM found for this Gate Review.",
                        { type: "warning", title: doc.format_name || "Gate Review" }
                    );
                }
            } catch (err) {
                console.error("[APQP] action_open_phase_mom failed:", err);
                this.notification.add(
                    err.message || "Failed to open MOM for Gate Review.",
                    { type: "danger", title: "Error" }
                );
            } finally {
                this.state.loadingDocId = null;
            }
            return;
        }

        // ── Case 1: attachment / confirmation source → open standard Odoo form ─
        if (
            doc.source === "attachment" ||
            doc.document_type === "attachment" ||
            doc.document_type === "confirmation"
        ) {
            const model = doc.source === "attachment"
                ? "apqp.timeline.attachment"
                : "apqp.timeline.format";
            return this._openOdooForm(doc, model);
        }

        // ── Case 2: format source with an IATF type ───────────────────────────
        if (doc.source === "format" && doc.iatf_type) {

            // Sub-case A: formate NOT yet created → auto-create then open HTML view
            if (!doc.formate_id) {

                if (!doc.document_approval_id) {
                    // No linked document.approval at all — fall back to plain form
                    this.notification.add(
                        "No document approval record linked. Opening form view.",
                        { type: "warning", title: doc.format_name }
                    );
                    return this._openOdooForm(doc, "apqp.timeline.format");
                }

                this.state.loadingDocId = doc.id;
                try {
                    // Step 1: call create_formate — this creates the IATF record
                    //         and returns an act_window action (ignored here)
                    await rpc("/web/dataset/call_kw", {
                        model:  "document.approval",
                        method: "create_formate",
                        args:   [[doc.document_approval_id]],
                        kwargs: {},
                    });

                    // Step 2: now open the HTML full view for this iatf_type
                    const htmlAction = await rpc("/web/dataset/call_kw", {
                        model:  "apqp.timeline.chart",
                        method: "action_open_iatf_full_view",
                        args:   [[doc.chart_id], doc.iatf_type],
                        kwargs: {},
                    });
                    if (htmlAction) {
                        return this.actionService.doAction(htmlAction);
                    }
                } catch (err) {
                    console.error("[APQP] create_formate / full view failed:", err);
                    this.notification.add(
                        err.message || "Failed to create and open document.",
                        { type: "danger", title: "Error" }
                    );
                } finally {
                    this.state.loadingDocId = null;
                }
                return;
            }

            // Sub-case B: formate already created → open HTML full view directly
            this.state.loadingDocId = doc.id;
            try {
                const htmlAction = await rpc("/web/dataset/call_kw", {
                    model:  "apqp.timeline.chart",
                    method: "action_open_iatf_full_view",
                    args:   [[doc.chart_id], doc.iatf_type],
                    kwargs: {},
                });
                if (htmlAction) {
                    return this.actionService.doAction(htmlAction);
                }
            } catch (err) {
                console.warn(
                    `[APQP] Full view failed for iatf_type="${doc.iatf_type}", ` +
                    `falling back to standard form. Error:`, err
                );
                // Graceful fallback to plain Odoo form
                return this._openOdooForm(doc, "apqp.timeline.format");
            } finally {
                this.state.loadingDocId = null;
            }
            return;
        }

        // ── Case 3: format source with no IATF type → plain form ─────────────
        return this._openOdooForm(doc, "apqp.timeline.format");
    }
    // ─────────────────────────────────────────────────────────────────────────

    _openOdooForm(doc, model) {
        const title = doc.format_name || (model === "apqp.timeline.attachment" ? "Attachment" : "Format");
        this.actionService.doAction({
            type:      "ir.actions.act_window",
            name:      title,
            res_model: model,
            res_id:    doc.id,
            view_mode: "form",
            views:     [[false, "form"]],
            target:    "new",
            context:   { create: false },
        });
    }

    onViewDocsClick() {
        this.props.onViewDocs(this.props.phase);
    }

    formatDate(dateStr) {
        if (!dateStr) return '';
        const [y, m, d] = dateStr.split('-');
        return `${d}/${m}/${y.slice(2)}`;
    }
}

// ─── Main Dashboard Component ─────────────────────────────────────────────────
class APQPFlowchartDashboard extends Component {
    static template = "apqp.FlowchartDashboard";
    static components = { PhaseCard };

    setup() {
        this.actionService = useService("action");
        this.notification  = useService("notification");

        // ✅ React to browser Back/Forward while this dashboard is open.
        // Since PhaseCard.onDocClick pushes a history entry before opening a
        // doc, pressing Back will fire popstate and land the user back here
        // instead of jumping straight to the previous Odoo page.
        this._onPopState = (ev) => {
            // No extra action needed — returning to this pushed state simply
            // keeps the dashboard mounted. This listener exists so future
            // doc-specific restore logic (e.g. re-opening a doc from
            // ev.state.apqpSlug) can be added here if ever needed.
        };
        window.addEventListener("popstate", this._onPopState);

        // Try params first, then fall back to extracting from URL
        let chartId = this.props.action?.params?.chart_id || null;

        if (!chartId) {
            const urlMatch =
                window.location.pathname.match(/\/(\d+)\/apqp_flowchart_dashboard/) ||
                window.location.pathname.match(/apqp\.timeline\.chart\/(\d+)/);
            if (urlMatch) {
                chartId = parseInt(urlMatch[1]);
            }
        }

        console.log("[APQP] Dashboard setup, chartId =", chartId);
        this.chartId = chartId;

        this.state = useState({
            loading: true,
            error:   null,
            data:    null,
        });

        onMounted(() => {
            if (!this.chartId) {
                this.state.error = "Could not determine chart ID. Please reopen from the Timeline Chart.";
                this.state.loading = false;
                return;
            }
            this._loadData();
            this._onKeydown = (e) => { if (e.key === "Escape") this._close(); };
            document.addEventListener("keydown", this._onKeydown);

            // Hide Odoo navbar and breadcrumbs
            document.querySelector('.o_main_navbar')?.style.setProperty('display', 'none', 'important');
            document.querySelector('.o_breadcrumb')?.style.setProperty('display', 'none', 'important');
            document.querySelector('.o_control_panel')?.style.setProperty('display', 'none', 'important');
        });

        onWillUnmount(() => {
            document.removeEventListener("keydown", this._onKeydown);
            window.removeEventListener("popstate", this._onPopState);

            // Restore Odoo navbar and breadcrumbs
            document.querySelector('.o_main_navbar')?.style.removeProperty('display');
            document.querySelector('.o_breadcrumb')?.style.removeProperty('display');
            document.querySelector('.o_control_panel')?.style.removeProperty('display');
        });
    }

    async _loadData() {
        try {
            console.log("[APQP] Loading flowchart data for chartId:", this.chartId);
            const data = await rpc(`/apqp/flowchart_data/${this.chartId}`);

            if (data.error) {
                this.state.error = data.error;
                console.error("[APQP] Controller returned error:", data.error);
            } else {
                this.state.data = data;

                for (const phase of data.phases || []) {
                    const iatfDocs = phase.documents.filter(d => d.iatf_type);
                    if (iatfDocs.length) {
                        console.log(`[APQP] Phase "${phase.name}" IATF docs:`,
                            iatfDocs.map(d => ({
                                name:                 d.format_name,
                                iatf_type:            d.iatf_type,
                                document_type:        d.document_type,
                                source:               d.source,
                                chart_id:             d.chart_id,
                                document_approval_id: d.document_approval_id,
                                formate_id:           d.formate_id,
                            }))
                        );
                    }
                    const gateReviewDocs = phase.documents.filter(d => d.is_gate_review);
                    if (gateReviewDocs.length) {
                        console.log(`[APQP] Phase "${phase.name}" Gate Review docs:`,
                            gateReviewDocs.map(d => ({
                                name:          d.format_name,
                                id:            d.id,
                                is_gate_review: d.is_gate_review,
                                activity:      d.activity,
                            }))
                        );
                    }
                }
            }
        } catch (e) {
            this.state.error = "Failed to load flowchart data.";
            console.error("[APQP] _loadData FAILED:", e);
        } finally {
            this.state.loading = false;
        }
    }

    async onGanttClick() {
        const action = await rpc("/web/dataset/call_kw", {
            model:  "apqp.timeline.chart",
            method: "action_open_gantt",
            args:   [[this.chartId]],
            kwargs: {},
        });
        this.actionService.doAction(action);
    }

    async onMomClick() {
        const action = await rpc("/web/dataset/call_kw", {
            model:  "apqp.timeline.chart",
            method: "action_open_mom_report",
            args:   [[this.chartId]],
            kwargs: {},
        });
        this.actionService.doAction(action);
    }

    _close() {
        this.actionService.restore();
    }

    _onViewDocs(phase) {
        this.notification.add(
            `${phase.name}: ${phase.total_docs} document(s)`,
            { type: "info", title: phase.name }
        );
    }

    get phases() {
        return this.state.data?.phases || [];
    }
}

// ─── Register client action ───────────────────────────────────────────────────
registry.category("actions").add("apqp_flowchart_dashboard", APQPFlowchartDashboard);

export { APQPFlowchartDashboard, PhaseCard };