{
    'name': 'Módulo de Prueba',
    'version': '16.0',
    'description': 'Modulo para probar cosas',
    'summary': 'Tests',
    'author': 'Rivas Rodrigo',
    'website': '',
    'license': 'LGPL-3',
    'category': 'Other',
    'depends': [
        'base', 'account',
    ],
    'data': [
        'security/top_management_security.xml',
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/res_config_settings_views.xml',
        'views/account_share_issuance.xml'
        'views/menu_view.xml',
        'views/test_line_views.xml',
        'views/test_line.xml',
        'views/menu_view.xml',
    ],
    'demo': [
        # 'demo/estate.property.demo.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'web.assets_backend': [
            'pruebas/static/src/**/*',
            'pruebas/static/src/xml/**/*',
        ],
        'web.report_assets_pdf': [

        ],
    }
}