{
    'name': 'Account Share Management',
    'version': '16.0',
    'description': 'Módulo que crea los modelos básicos a ser usados para el libro de acciones',
    'summary': 'Accionistas, Acciones, Suscripciones, integraciones, inversiones',
    'author': 'Rivas Rodrigo',
    'website': '',
    'license': 'LGPL-3',
    'category': 'Accounting',
    'depends': [
        'account_financial_policies','purchase'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'report/account_share_issuance_template.xml',
        'report/account_share_issuance_report.xml',
        'report/account_share_template.xml',
        'report/account_share_report.xml',
        'views/res_partner.xml',
        'views/account_share_view.xml',
        'views/account_share_issuance.xml',
        'views/purchase.xml',
        'views/account_share_type.xml',
        'views/menu_view.xml',
    ],
    'demo': [
        
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        
    }
}