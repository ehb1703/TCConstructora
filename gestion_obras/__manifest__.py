# -*- coding: utf-8 -*-
{
    'name': 'Gestión de Obras',
    'version': '18.0.1.1.0',
    'summary': 'Contratos y subcontratos de obra con candado de expediente digital',
    'sequence': 165,
    'description': """
Gestión de Obras
====================
Motor de reglas de negocio para contratistas y proveedores de obra.
Submódulos de esta versión:
- Expediente digital y gobernanza contractual (sobre el expediente de contactos de project_extra).
- Contratos y subcontratos.
- Presupuesto Kontrol: base congelada, aditivas, deductivas, extraordinarios y órdenes de cambio.
- Contabilidad analítica Kontrol: planes N1 a N5, N1 obligatorio, frente y partida en las tareas.
- Matriz jerárquica de autorizaciones: niveles 1 a 4, candados de aprobación y ordenación exclusiva de pagos.
    """,
    'category': 'Gestión de Obras',
    'depends': ['base', 'mail', 'account', 'analytic', 'purchase', 'hr_timesheet', 'sale_timesheet', 'stock_analytic', 'account_batch_payment', 'project_extra'],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/ir_sequence.xml',
        'data/tipos_contratista_data.xml',
        'data/kontrol_analitica_data.xml',
        'views/gestion_obra_contrato_views.xml',
        'views/gestion_obra_presupuesto_views.xml',
        'views/crm_presupuesto_views.xml',
        'views/gestion_obra_modificacion_views.xml',
        'views/project_task_views.xml',
        'views/pagos_views.xml',
    ],
    'demo': [
        'data/kontrol_analitica_demo.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False
}
