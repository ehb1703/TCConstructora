# -*- coding: utf-8 -*-
{
    'name': 'Reporteria',
    'version': '1.0',
    'summary': 'Reporteria',
    'sequence': 151,
    'icon': '/reports/static/description/iconr.png',
    'description': """
Reporteria
====================
Información para la generación de tableros en Power BI
Configuración de estructura de documentos
    """,
    'category': 'Reporteria',
    'depends': ['base', 'contacts'],
    'data': [        
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'views/report_requisition_views.xml',
        'views/report_document_views.xml',
    ],        
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False
}
