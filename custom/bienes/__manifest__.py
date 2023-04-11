{
    'name': 'Propiedades',
    'version': '1.0',
    'description': 'Módulo que permite la gestion, compra y venta de Terrenos, y su correspondiente valuación',
    'summary': 'Terrenos, modelo por herencia delegacion,',
    'author': 'Rivas Rodrigo',
    'website': '',
    'license': 'LGPL-3',
    'category': 'Real Estate/Brokerage',
    'depends': [
        'base', 'account_asset_management'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/estate_property_security.xml',
        'views/estate_property_views.xml',
        'views/estate_property_type_view.xml',
        'views/estate_property_tag_view.xml',
        'views/estate_property_offer_view.xml',
        'views/account_asset_view.xml',
        'views/res_users_view.xml',
        'data/estate.property.type.csv',
        'report/estate_report_templates.xml',
        'report/estate_reports.xml'
    ],
    'demo': [
        'demo/estate.property.demo.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        
    }
}