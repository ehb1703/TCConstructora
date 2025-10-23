# -*- coding: utf-8 -*-
{
    'name': 'Extra de contactos',
    'version': '1.0',
    'summary': 'Extra de contactos',
    'sequence': 151,
    'description': """
Extra de contactos
====================
Personalización de catálogos
    """,
    'category': 'Contacts',
    'depends': ['base', 'contacts', 'account'],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'views/catalogs_views.xml',
        'views/res_company_views.xml',
    ],        
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False
}