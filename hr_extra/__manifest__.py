# -*- coding: utf-8 -*-
{
    'name': 'HR Extra',
    'version': '1.1',
    'category': 'Human Resources/Payroll',
    'sequence': 290,
    'summary': 'Extensiones de Recursos Humanos para TC Constructora',
    'description': """
        Módulo de extensiones para Recursos Humanos:
            - Catálogo de Parentescos
            - Beneficiarios en contratos de empleados
            - Asignación de obras a empleados
            - API de descarga de asistencias de checadores (ctrol.asistencias)
            - Mejoras API - paginación completa, validaciones de fecha
	    - Procesamiento automático de asistencias a Odoo (hr.attendance, hr.attendance.overtime, hr.work.entry)
        Reportería
           - Reportes de contratos (Temporal, Obra Determinada)
           - Convenio de Confidencialidad
    """,
    'installable': True,
    'application': True,
    'depends': ['hr_payroll', 'hr_contract', 'project', 'project_extra'],
    'data': [
        'data/ir_cron_attendance.xml',
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'views/hr_catalogs_views.xml',
        'views/hr_employee_views.xml',
        'views/resource_calendar_views.xml',
        'views/res_config_settings_views.xml',
        'views/ctrol_asistencias_views.xml',
        'views/checador_sync_log_views.xml',
        'views/hr_leaves_views.xml',
        'report/hr_contract_report.xml',
        'report/report_hr_contract_prueba.xml',
        'report/report_hr_contract_obra.xml',
        'report/report_hr_contract_indeterminado.xml',
        'report/report_convenio_confidencialidad.xml',
    ],
    'external_dependencies': {
        'python': ['jwt'],  # PyJWT
    },
    'auto_install': False,
    'license': 'LGPL-3',
}
