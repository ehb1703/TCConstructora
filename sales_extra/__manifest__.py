# -*- coding: utf-8 -*-
{
    'name': 'Extra Productos y Precios',
    'version': '1.0',
    'summary': 'Extra de productos y precios',
    'sequence': 151,
    'description': """
Extra de Productos y Precios
====================
Personalización de catálogos
Personalización de ordenes de venta
    """,
    'category': 'Sales/Sales',
    'depends': ['base', 'product', 'sale_project'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_views.xml',
        'views/sale_catalog_views.xml',
        #'views/project_views.xml',
    ],        
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False
}
