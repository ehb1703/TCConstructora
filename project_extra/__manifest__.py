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
    'depends': ['base', 'project'],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'views/project_views.xml',
    ],        
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False
}