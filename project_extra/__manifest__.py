# -*- coding: utf-8 -*-
{
    'name': 'Extra Proyectos',
    'version': '1.3',
    'summary': 'Extra de proyectos',
    'sequence': 151,
    'description': """
Extra de Proyectos
====================
Personalización del modulo:
    Campos proyecto
    """,
    'category': 'Services/Project',
    'depends': ['base', 'crm', 'sale_crm', 'sale_purchase_project', 'project', 'hr', 'hr_holidays', 'documents', 'reports', 'product_unspsc', 'purchase_requisition', 'contact_extra'],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'data/mail_template_crm.xml',
        'data/mail_template_purchase.xml',
        'data/cron_visita.xml',
        'data/ir_sequence.xml',
        'data/ir_actions_server.xml',
        'data/tipo_campamento_data.xml',
        'data/capacidad_data.xml',
        'views/project_catalogs_views.xml',
        'views/project_views.xml',        
        'views/crm_catalog_views.xml',
        'views/crm_views.xml',
        'views/purchase_views.xml',
        'views/refrendo_views.xml',
        'wizard/crm_revert_stage_views.xml',
        'wizard/crm_cotizacion_insumos_views.xml',
        'report/purchase_contract_templates.xml',
    ],        
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False
}
