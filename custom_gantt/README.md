# Custom Gantt Chart — Odoo 18 Module

A fully featured custom Gantt chart module for **Odoo 18 Enterprise**.

## Features

| Feature | Detail |
|---|---|
| **Gantt view** | Drag-and-drop bars, dependency arrows, today line |
| **Task dependencies** | Many2many `depend_on_ids` / `dependent_ids` |
| **Milestones** | Diamond marker with auto date-lock |
| **Progress bars** | Per-task float progress rendered inside each bar |
| **Priority colouring** | SCSS accents on Normal / Important / Very Urgent / Critical |
| **Consolidation row** | Aggregate progress across grouped rows |
| **Kanban view** | Stage-grouped swimlanes with colour coding |
| **List & Form views** | Full CRUD with chatter/activity support |
| **Search panel** | Project & stage facets + custom filters |
| **Demo data** | Sample project, stages, tasks & tags |

## Models

```
gantt.task       – Core task (date_start, date_stop, progress, priority, …)
gantt.project    – Container for tasks with progress roll-up
gantt.stage      – Kanban/Gantt stages (sequence-ordered)
gantt.tag        – Coloured many2many tags
```

## Installation

1. Copy the `custom_gantt` folder into your Odoo `addons` path.
2. Update the Apps list (`Settings → Apps → Update Apps List`).
3. Search for **Custom Gantt Chart** and click **Install**.

> **Requires:** Odoo 18 **Enterprise** (the `web_gantt` module ships with Enterprise).

## Gantt View Attributes (Odoo 18)

```xml
<gantt
    date_start="date_start"
    date_stop="date_stop"
    default_group_by="user_id"
    color="color"
    progress="progress"
    thumbnail="user_id"
    dependency_field="depend_on_ids"
    dependency_inverted_field="dependent_ids"
    pill_label="True"
    default_scale="month"
    consolidation="progress"
    consolidation_max="{'user_id': 100}"
    display_unavailability="true"
    total_row="true"
/>
```

## Directory Structure

```
custom_gantt/
├── __init__.py
├── __manifest__.py
├── data/
│   └── demo_data.xml
├── models/
│   ├── __init__.py
│   ├── gantt_stage.py
│   ├── gantt_project.py
│   └── gantt_task.py          ← main model
├── security/
│   └── ir.model.access.csv
├── static/src/scss/
│   └── gantt_custom.scss      ← Gantt bar styling
└── views/
    ├── gantt_task_views.xml   ← Gantt, List, Form, Kanban, Search
    └── gantt_task_menus.xml   ← App menus
```
