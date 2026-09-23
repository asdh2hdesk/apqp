# -*- coding: utf-8 -*-
{
    'name': 'APQP Gantt Connector',
    'version': '18.0.1.0.0',
    'category': 'Project Management',
    'summary': 'Connector between APQP Timeline and Custom Gantt Chart',
    'description': """
        Integrates APQP Timeline with Custom Gantt Chart.
        - Synchronize APQP phases and tasks to Gantt tasks.
        - Bi-directional date synchronization.
        - One-click Gantt chart generation from APQP Timeline.
    """,
    'author': 'Custom Development',
    'depends': ['apqp', 'custom_gantt'],
    'data': [
        'views/apqp_timeline_chart_views_inherit.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'apqp_gantt_connector/static/src/js/gantt_widget.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
