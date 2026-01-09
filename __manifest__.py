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
Plan de cuentas contables
Asignación automática de cuentas no obsoletas en nuevos contactos
       - Actualiza propiedades por defecto al instalar
       - Menú para actualizar contactos existentes con cuentas obsoletas
    """,
    'category': 'Contacts',
    'depends': ['base', 'contacts', 'account'],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'views/models_catalogs_views.xml',
        'views/res_company_views.xml',
        'views/models_account_views.xml',
    ],        
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False
}
