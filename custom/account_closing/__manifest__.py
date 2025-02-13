{
    'name': 'Accounting Closing',
    'version': '16.0',
    'description': 'Utilidades Contables para Cierres de Ejercicio',
    'summary': 'Año Fiscal, Períodos, Cuentas de Resultados, Clasificación de Cuentas',
    'author': 'Rivas Rodrigo',
    'website': '',
    'license': 'LGPL-3',
    'category': 'Account/Accounting',
    'depends': [
        'base', 'account', 'account_fiscal_year','account_lock_date_update', 'account_fiscal_year_auto_create'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/account_closing_security.xml',
        'data/data.xml',
        'views/res_config_settings_views.xml',
        'views/account_fiscal_year_views.xml',
        'views/account_fiscal_period_views.xml',
        'views/account_closing_menu.xml',
        'views/account_move_views.xml',
    ],
    'demo': [
        # 'demo/estate.property.demo.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        
    }
}