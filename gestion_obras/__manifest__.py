# -*- coding: utf-8 -*-
{
    'name': 'Gestión de Obras',
    'version': '18.0.1.0.0',
    'summary': 'Contratos y subcontratos de obra con candado de expediente digital',
    'sequence': 165,
    'description': """
Gestión de Obras
====================
Motor de reglas de negocio para contratistas y proveedores de obra.
Submódulos de esta versión:
- Expediente digital y gobernanza contractual (sobre el expediente de contactos de project_extra).
- Contratos y subcontratos.
    """,
    'category': 'Gestión de Obras',
    'depends': ['base', 'mail', 'account', 'analytic', 'project_extra'],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/tipos_contratista_data.xml',
        'views/gestion_obra_contrato_views.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False
}
