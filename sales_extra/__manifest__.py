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
    """,
    'category': 'Sales/Sales',
    'depends': ['base', 'product'],
    'data': [
        'views/product_views.xml',
    ],        
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False
}