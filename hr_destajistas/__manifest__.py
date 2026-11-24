# -*- coding: utf-8 -*-
{
    'name': 'Destajistas TC',
    'version': '18.0.1.1.0',
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
- Casilla "Es destajista" en Contactos; Asistencias y Nómina no muestran destajistas.
- Consultas propias: asistencias y pagos de destajo (Requisiciones) de los destajistas.
    """,
    'category': 'Human Resources',
    'depends': ['hr_extra', 'project_extra', 'requisition_residents', 'hr_attendance', 'hr_payroll_holidays'],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/ir_sequence.xml',
        'data/resource_calendar.xml',
        'wizard/alta_destajista_views.xml',
        'views/reporte_asistencias_views.xml',
        'views/hr_employee_views.xml',
        'views/consultas_views.xml',
    ],
    'assets': {'web.assets_backend': ['hr_destajistas/static/src/js/ocultar_cog_menu.js']},
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
