# -*- coding: utf-8 -*-
{
    'name': 'Requisiciones',
    'version': '1.0',
    'summary': 'Requisiciones',
    'sequence': 160,
    'description': """
Requisiciones
====================
Captura de las requisiciones de los residentes de obras """,
    'category': 'Requisiciones',
    'depends': ['base', 'contacts', 'project_extra'],
    'data': [        
        'data/ir_sequence.xml',
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'views/requisition_residents_views.xml',
    ],        
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False
}