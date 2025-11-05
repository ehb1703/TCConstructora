# -*- coding: utf-8 -*-
{
    'name': 'Equipo',
    'version': '1.0',
    'summary': 'Vehiculos - Equipo',
    'sequence': 151,
    'description': """
Vehiculos - Equipo
====================
Personalización del modulo:
    Catalogos
    Integración del equipo (patrimonio)
    """,
    'category': 'Human Resources/Fleet',
    'depends': ['base', 'fleet'],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'views/catalogs_views.xml',
        'views/fleet_vehicle_views.xml',
    ],        
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False
}