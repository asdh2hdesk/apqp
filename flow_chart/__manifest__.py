# -*- coding: utf-8 -*-
{
    'name': 'APQP Flow Chart',
    'version': '18.0.1.0.0',
    'license': 'AGPL-3',
    'description': """
        APQP Flow Chart Module
    """,
    'author': 'Megha',
    'depends': ['xf_doc_approval', 'iatf', 'mail'],
    'data': [
        'views/apqp_flowchart_button_views.xml',
        'views/document_package_inherit_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'flow_chart/static/src/css/apqp_flowchart.css',
            'flow_chart/static/src/xml/apqp_flowchart_templates.xml',
            'flow_chart/static/src/js/apqp_flowchart.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
