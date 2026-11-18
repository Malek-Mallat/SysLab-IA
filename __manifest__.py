{
    'name': "SysLab - Laboratoire d'Analyses",
    'version': '17.0.1.0.0',
    'summary': "Gestion d'un laboratoire d'analyses medicales avec interpretation assistee par IA",
    'description': "ERP Odoo pour laboratoire d'analyses medicales : patients, demandes, resultats, interpretation par regles et couche Machine Learning.",
    'author': 'Malek Mallat',
    'category': 'Services',
    'depends': ['base', 'mail', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/analyse_data.xml',
        'data/company_data.xml',
        'report/demande_report.xml',
        'data/mail_template.xml',
        'views/analyse_views.xml',
        'views/patient_views.xml',
        'views/medecin_views.xml',
        'views/demande_views.xml',
        'views/resultat_views.xml',
        'views/dashboard_views.xml',
        'views/res_company_views.xml',
        'views/menus.xml',
    ],
    # Fichiers front-end du tableau de bord (composant OWL)
    'assets': {
        # Couleur generale du backend (teal) : variables chargees AVANT celles d'Odoo
        'web._assets_primary_variables': [
            ('prepend', 'syslab/static/src/scss/primary_variables.scss'),
        ],
        'web.assets_backend': [
            'syslab/static/src/dashboard/dashboard.js',
            'syslab/static/src/dashboard/dashboard.xml',
            'syslab/static/src/dashboard/dashboard.scss',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
