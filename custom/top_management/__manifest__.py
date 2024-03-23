{
    'name': 'Top Management',
    'version': '16.0',
    'description': 'Módulo que permite la gestion de Gerencias y Asambleas de Accionistas',
    'summary': 'Accionistas, Acciones, Suscripciones, integraciones, inversiones',
    'author': 'Rivas Rodrigo',
    'website': '',
    'license': 'LGPL-3',
    'category': 'Shareholding',
    'depends': [
        'base', 'account','account_fiscal_year','account_share_management', 'hr_attendance',
        'account_lock_date_update', 'account_fiscal_year_auto_create', 'event'
    ],
    'data': [
        'security/top_management_security.xml',
        'security/security_rules.xml',
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/res_config_settings_views.xml',
        'views/account_share_issuance.xml',
        'views/event_view.xml',
        'views/assembly_vote.xml',
        'views/assembly_meeting.xml',
        'views/assembly_meeting_topic.xml',
        'views/assembly_meeting_line.xml',
        'views/hr_attendance_view.xml',
        'views/res_partner_position.xml',
        'views/res_partner.xml',
        'views/hr_employee.xml',
        'views/french_action.xml',
        'report/assembly_meeting_template.xml',
        'report/assembly_meeting_vote_template.xml',
        'report/assembly_meeting_report.xml',
        'wizard/wizard_create_vote.xml',
        'wizard/message_wizard.xml',
        'views/menu_view.xml',
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
            '/top_management/static/src/scss/normalize.scss',
            '/top_management/static/src/scss/assembly_meeting_report.scss',
            '/top_management/static/src/scss/assembly_meeting_vote_report.scss',
        ],
    }
}