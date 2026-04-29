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
    'depends': ['base', 'mail', 'contacts', 'project_extra'],
    'data': [        
        'data/ir_sequence.xml',
        'data/ir_action_server.xml',
        'data/mail_template_req.xml',
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'views/requisition_residents_views.xml',
        'views/requisition_movimientos_views.xml',
        'views/requisition_materials_views.xml',
        'views/requisition_concepts_views.xml',
        'views/requisition_hr_solicitud_views.xml',
        'wizard/wizard_generate_requisition.xml',
        'wizard/wizard_generate_transfer.xml',
        'wizard/wizard_rechazar_solicitud_views.xml',
    ],        
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False
}
