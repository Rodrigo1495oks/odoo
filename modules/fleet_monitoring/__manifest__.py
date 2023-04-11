# -*- coding: utf-8 -*-
{
    'name': 'Fleet Monitoring',
    'version': '16.0.0.0.0',
    'summary': 'Handle live fleet monitoring on map',
    'author': 'RKO',
    'company': 'RKO',
    'website': '',
    'price': 0,
    'currency': 'USD',
    'category': 'Human Resources',
    'maintainer': 'RKO',

    # any module necessary for this one to work correctly
    'depends': ['base', 'fleet', 'base_geolocalize'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/banner.gif'],
    'assets': {
        'web.assets_backend': [
            'fleet_monitoring/static/src/**/*',
        ],
    },
    'license': 'AGPL-3',
}
