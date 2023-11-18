{
    'name': 'Higher Authority',
    'version': '16.0',
    'description': 'Módulo que permite la gestion de Alta direccion',
    'summary': 'Accionistas, Acciones, Suscripciones, integraciones, inversiones',
    'author': 'Rivas Rodrigo',
    'website': '',
    'license': 'LGPL-3',
    'category': 'Shareholding',
    'depends': [
        'base', 'account','account_fiscal_year','account_lock_date_update', 'account_fiscal_year_auto_create'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/higher_authority_security.xml',
        'data/data.xml',
        'views/account_shareholder.xml',
        'views/res_partner.xml',
        'views/menu_view.xml',
        'views/res_config_settings_views.xml',
        # 'views/res_users_view.xml',
        # 'data/estate.property.type.csv',
        # 'report/estate_report_templates.xml',
        # 'report/estate_reports.xml'
    ],
    'demo': [
        # 'demo/estate.property.demo.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        
    }
}