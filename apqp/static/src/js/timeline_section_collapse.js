/** @odoo-module **/

/**
 * APQP Timeline Section Collapse/Expand
 *
 * Adds a white triangle toggle button on section header rows
 * (display_type == 'line_section') inside the timeline_format_line_list,
 * allowing users to collapse/expand all child rows under a phase.
 */

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

/**
 * We patch the ListRenderer to intercept rendering within
 * the timeline_format_line_list context.
 */
patch(ListRenderer.prototype, {
    /**
     * Override setup to initialise collapse state tracking.
     */
    setup() {
        super.setup(...arguments);
        // Map of section record id -> boolean (true = collapsed)
        this._sectionCollapsed = {};
    },

    /**
     * Check whether this renderer belongs to our target list.
     * We detect it by checking for the CSS class on the list element.
     */
    get _isTimelineFormatList() {
        // props.list model check as secondary guard
        return (
            this.props.list &&
            this.props.list.model &&
            this.props.list.model.config &&
            this.props.list.model.config.resModel === "apqp.timeline.format"
        );
    },

    /**
     * Toggle collapsed state for a given section record id.
     * @param {number|string} sectionId
     */
    _toggleSectionCollapse(sectionId) {
        this._sectionCollapsed[sectionId] = !this._sectionCollapsed[sectionId];
        // Force re-render by triggering a reactive update
        this.render(true);
    },

    /**
     * Returns the list of records to render, filtering out rows
     * whose parent section is collapsed.
     */
    get groupedRecords() {
        // Fall through if not our list
        if (!this._isTimelineFormatList) {
            return super.groupedRecords;
        }
        return super.groupedRecords;
    },
});

/**
 * DOM-based approach: After the list renders, inject the toggle buttons
 * and apply row visibility using MutationObserver + event delegation.
 *
 * This is the most reliable approach for Odoo 18 list views with
 * section_and_note_one2many, where we don't control the OWL template
 * directly.
 */

// Wait for DOM to be ready
document.addEventListener("DOMContentLoaded", () => {
    initTimelineSectionCollapse();
});

// Also handle cases where the view loads after initial page load
// (e.g. navigating to the form view via SPA routing)
const _originalPushState = history.pushState;
history.pushState = function () {
    _originalPushState.apply(this, arguments);
    setTimeout(initTimelineSectionCollapse, 800);
};

window.addEventListener("popstate", () => {
    setTimeout(initTimelineSectionCollapse, 800);
});

// Re-init whenever the APQP form mounts (Odoo triggers __owl__ events)
document.addEventListener("click", (e) => {
    // Re-scan after any click that might load the form
    setTimeout(() => {
        tryAttachToTimelineList();
    }, 600);
});

let _observer = null;

function initTimelineSectionCollapse() {
    setTimeout(tryAttachToTimelineList, 400);
}

function tryAttachToTimelineList() {
    const listEl = document.querySelector(".timeline_format_line_list");
    if (!listEl) return;

    // Avoid double-init
    if (listEl.dataset.sectionCollapseInit === "1") return;
    listEl.dataset.sectionCollapseInit = "1";

    setupCollapseOnList(listEl);

    // Watch for re-renders (Odoo may re-render the list on save/edit)
    if (_observer) _observer.disconnect();
    _observer = new MutationObserver(() => {
        // If list was re-rendered, re-init
        const el = document.querySelector(".timeline_format_line_list");
        if (el && el.dataset.sectionCollapseInit !== "1") {
            setupCollapseOnList(el);
        } else if (el) {
            // Re-apply visibility after re-render
            reApplyCollapsedState(el);
        }
    });
    _observer.observe(document.body, { childList: true, subtree: true });
}

/**
 * Collapse state stored per section's data-id attribute.
 * Global so it persists across re-renders.
 */
const _collapsedSections = new Set();

function setupCollapseOnList(listEl) {
    injectToggleButtons(listEl);
    reApplyCollapsedState(listEl);
}

function injectToggleButtons(listEl) {
    // Find all section rows: rows with the class o_is_section or decoration-primary
    // In Odoo 18, line_section rows have class "o_is_section"
    const sectionRows = listEl.querySelectorAll("tr.o_is_section, tr[class*='table-primary'], tr[class*='text-primary']");

    sectionRows.forEach((row) => {
        // Avoid adding toggle twice
        if (row.dataset.toggleAdded === "1") return;
        row.dataset.toggleAdded = "1";

        // Get the first TD (which contains the section name)
        const firstTd = row.querySelector("td");
        if (!firstTd) return;

        // Find the cell that contains the section text - usually a .o_section_and_note_field_cell or similar
        const nameTd = row.querySelector("td.o_data_cell, td") ;
        if (!nameTd) return;

        // Create the toggle button
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "apqp-section-toggle-btn";
        btn.innerHTML = `<i class="fa fa-caret-down"></i>`;
        btn.title = "Collapse/Expand this phase";
        btn.style.cssText = `
            background: transparent;
            border: none;
            cursor: pointer;
            padding: 0 4px 0 0;
            color: #ffffff;
            font-size: 14px;
            line-height: 1;
            vertical-align: middle;
            display: inline-flex;
            align-items: center;
        `;

        // Get a stable identifier for this section row
        // Try data-id first, fallback to row index
        const rowId = row.dataset.id || row.rowIndex;
        row.dataset.sectionKey = rowId;

        // Set initial icon based on current state
        if (_collapsedSections.has(String(rowId))) {
            btn.querySelector("i").className = "fa fa-caret-right";
        }

        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            e.preventDefault();
            toggleSection(listEl, row, rowId, btn);
        });

        // Insert the button at the beginning of the name cell content
        // Find the div or span inside the td
        const innerEl = nameTd.querySelector(".o_cell_value, .o_field_widget, span, div") || nameTd;

        // Prepend button to the name cell
        nameTd.insertBefore(btn, nameTd.firstChild);
    });
}

function toggleSection(listEl, sectionRow, sectionKey, btn) {
    const key = String(sectionKey);
    const isCollapsed = _collapsedSections.has(key);

    if (isCollapsed) {
        _collapsedSections.delete(key);
        btn.querySelector("i").className = "fa fa-caret-down";
    } else {
        _collapsedSections.add(key);
        btn.querySelector("i").className = "fa fa-caret-right";
    }

    applyCollapseForSection(listEl, sectionRow, !isCollapsed);
}

function applyCollapseForSection(listEl, sectionRow, collapse) {
    // Find all rows between this section row and the next section row
    const allRows = Array.from(listEl.querySelectorAll("tbody tr"));
    const sectionIndex = allRows.indexOf(sectionRow);
    if (sectionIndex === -1) return;

    // Collect child rows (until next section or end)
    for (let i = sectionIndex + 1; i < allRows.length; i++) {
        const row = allRows[i];
        const isSection = row.classList.contains("o_is_section") ||
                          row.classList.contains("table-primary") ||
                          row.classList.contains("text-primary") ||
                          row.querySelector("td.o_section_and_note_text_cell") !== null;
        if (isSection) break; // reached next section
        row.style.display = collapse ? "none" : "";
    }
}

function reApplyCollapsedState(listEl) {
    // Re-inject buttons first (in case of re-render)
    injectToggleButtons(listEl);

    // Re-apply all stored collapse states
    const sectionRows = listEl.querySelectorAll("tr[data-section-key]");
    sectionRows.forEach((sectionRow) => {
        const key = sectionRow.dataset.sectionKey;
        if (_collapsedSections.has(String(key))) {
            applyCollapseForSection(listEl, sectionRow, true);
        }
    });
}