# -*- coding: utf-8 -*-
{
    'name': 'Custom Gantt Chart',
    'version': '18.0.4.0.0',
    'category': 'Project',
    'summary': 'Custom Gantt chart for Odoo 18 Community',
    'author': 'Custom Development',
    'depends': ['base', 'mail', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'data/mom_access.xml',
        'views/gantt_task_views.xml',
        'views/gantt_mom_views.xml',
        'views/gantt_task_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_gantt/static/src/js/gantt_view.js',
            'custom_gantt/static/src/scss/gantt_custom.scss',
        ],
    },
    'demo': ['data/demo_data.xml'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
