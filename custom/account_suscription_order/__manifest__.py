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
        'base', 'account','top_management','account_asset_management','top_management','purchase','purchase_stock','account_payment_group'
    ],
    'data': [
        'security/security_rules.xml',
        'security/ir.model.access.csv',
        'data/data.xml',
        'data/order_stage.xml',
        'views/account_move_views.xml',
        'views/account_stock_quote_views.xml',
        'views/res_config_settings_views.xml',
        'views/order_stage_views.xml',
        'views/account_suscription_order.xml',
        'views/order_line_views.xml',
        'views/assembly_meeting_topic.xml',
        'wizard/wizard_confirm.xml',
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