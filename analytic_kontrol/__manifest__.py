# -*- coding: utf-8 -*-
{
    'name': 'Analítica Kontrol (T0110)',
    'version': '18.0.1.0.0',
    'summary': 'Planes analíticos N1-N5 y obligatoriedad de N1 para el presupuesto Kontrol',
    'sequence': 152,
    'description': """
Analítica Kontrol (T0110)
=========================
Configuración de la contabilidad analítica para el presupuesto Kontrol:
    5 planes raíz: N1 Obra, N2 Frente, N3 Partida, N4 Concepto, N5 Insumo
    El plan 'Project' existente pasa a ser N1 OBRA (conserva sus cuentas)
    N1 obligatorio en pedidos de compra, facturas de proveedor, partes de horas y almacén
    Ejemplo: HOSPITAL CIVIL ORIENTE / F1 / A2.1 CIMENTACION
    """,
    'category': 'Accounting/Accounting',
    'depends': ['analytic', 'account', 'purchase', 'hr_timesheet', 'stock_analytic'],
    'data': [
        'data/planes_data.xml',
        'data/obligatoriedad_data.xml',
        'data/ejemplo_data.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
