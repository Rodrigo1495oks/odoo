{
    'name': 'Account Suscription Order Stock',
    'version': '16.0',
    'description': 'Module that allows the receipt of stock in subscription orders',
    'summary': 'Shareholders, Shares, Subscriptions, integrations, investments',
    'author': 'Rivas Rodrigo',
    'website': '',
    'license': 'LGPL-3',
    'category': 'Shareholding',
    'depends': [
        'base', 'account','top_management','account_asset_management','purchase','purchase_stock','account_payment_group'
    ],
    'data': [
        'views/account_move_views.xml',
        'views/account_suscription_order.xml',
        'views/stock_lot_views.xml',
        'views/stock_moves.xml',

    ],
    'demo': [
        # 'demo/estate.property.demo.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'web.assets_backend': [

        ],
        'web.report_assets_pdf': [

        ],
    }
}