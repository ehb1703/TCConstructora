# -*- coding: utf-8 -*-
{
    'name': 'Catálogo Único de Insumos TC',
    'version': '18.0.1.3.0',
    'summary': 'Catálogo único de insumos con memoria de equivalencias y conciliación de licitaciones',
    'sequence': 166,
    'description': """
Catálogo Único de Insumos TC
============================
- Un producto por insumo para todas las obras; identidad = consecutivo de 5 dígitos asignado por Odoo.
- Clave TC (tipo-categoría-familia-consecutivo) como referencia interna, calculada.
- Memoria de equivalencias: fuente + código externo (de cada presupuesto) -> insumo.
- Conciliación al generar los insumos de una licitación: automático, sugerido, conflicto o alta nueva.
- Alta asistida y reclasificación solo por el Administrador del Catálogo.
    """,
    'category': 'Inventory/Purchase',
    'depends': ['purchase', 'crm', 'project_extra', 'sales_extra'],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'wizard/importar_wizard_views.xml',
        'views/catalogo_views.xml',
        'views/crm_views.xml',
        'wizard/alta_wizard_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
