{
    'name': 'Account Financial Policies',
    'version': '16.0',
    'description': 'Este módulo crea la configuración contable básica para el departamento de Planificación y Política Financiera',
    'summary': 'Accionistas, Acciones, Suscripciones, integraciones, inversiones',
    'author': 'Rivas Rodrigo',
    'website': '',
    'license': 'LGPL-3',
    'category': 'Finance',
    'depends': [
        'base', 'account', 'account_utilities'
    ],
    'data': [
        # Importamos las vistas y creamos el menu para Finanzas
        'security/account_financial_policies_security.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner.xml',
        'views/res_company.xml',
        'views/menu_view.xml',
    ],
    'demo': [
        # 'demo/estate.property.demo.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        
    }
}