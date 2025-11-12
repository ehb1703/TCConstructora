# -*- coding: utf-8 -*-
{
    'name': 'Extra Proyectos',
    'version': '1.0',
    'summary': 'Extra de proyectos',
    'sequence': 151,
    'description': """
Extra de Proyectos
====================
Personalización del modulo:
    Campos proyecto
    """,
    'category': 'Services/Project',
    'depends': ['base', 'project', 'crm', 'sale_purchase_project'],
    'data': [
        'data/mail_template_calificado.xml',
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'views/project_views.xml',
        'views/models_crm_views.xml',
        'views/crm_catalog_views.xml',
        'views/crm_views.xml',
        'wizard/crm_revert_stage_views.xml',
    ],        
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False
}
