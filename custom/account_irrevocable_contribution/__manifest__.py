{
    'name': 'Irrevocable contributions for future share subscriptions',
    'version': '16.0',
    'description': 'Module that allows the management of Irrevocable contributions for future share subscriptions',
    'summary': 'Shareholders, Shares, Subscriptions, integrations, investments',
    'author': 'Rivas Rodrigo',
    'website': '',
    'license': 'LGPL-3',
    'category': 'Shareholding',
    'depends': [
        'base', 'account_suscription_order'
    ],
    'data': [
        'security/security_rules.xml',
        'security/ir.model.access.csv',

    ],
    'demo': [
        # 'demo/estate.property.demo.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'web.assets_backend': [
            'top_management/static/src/**/*',
            'top_management/static/src/xml/**/*',
        ],
        'web.report_assets_pdf': [

        ],
    }
}