{
    'name': 'Account Suscription Order',
    'version': '16.0',
    'description': 'Module that allows the management of Share Subscription',
    'summary': 'Shareholders, Shares, Subscriptions, integrations, investments',
    'author': 'Rivas Rodrigo',
    'website': '',
    'license': 'LGPL-3',
    'category': 'Shareholding',
    'depends': [
        'base', 'account','top_management','account_asset_management'
    ],
    'data': [
        'security/security_rules.xml',
        'security/ir.model.access.csv',
        'views/account_stock_quote_views.xml',
        'views/menu_item.xml',
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