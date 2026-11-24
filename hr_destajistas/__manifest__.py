# -*- coding: utf-8 -*-
{
    'name': 'Destajistas TC',
    'version': '18.0.1.0.0',
    'summary': 'Registro de destajistas de obra, checadores y reporte de asistencias, separados del padrón de empleados y fuera de nómina',
    'sequence': 167,
    'description': """
Destajistas TC (T0134)
======================
- Alta rápida del destajista (nombre, CURP, NSS, fotografía, cuenta bancaria, obra y residente responsable).
- Tipo de personal (Empleado / Destajista) para filtros, consultas y reportes.
- Numeración propia D0001 para los checadores; las checadas se procesan sin contrato y no participan en nómina.
- API de checadores: una checada reenviada se actualiza en lugar de duplicarse.
- Reporte de asistencias: solo empleados, solo destajistas o ambos.
    """,
    'category': 'Human Resources',
    'depends': ['hr_extra', 'project_extra', 'requisition_residents'],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/ir_sequence.xml',
        'data/resource_calendar.xml',
        'wizard/alta_destajista_views.xml',
        'views/reporte_asistencias_views.xml',
        'views/hr_employee_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
