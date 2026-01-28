# -*- coding: utf-8 -*-
{
    'name': 'HR Extra',
    'version': '1.0',
    'category': 'Human Resources/Payroll',
    'sequence': 290,
    'summary': 'Extensiones de Recursos Humanos para TC Constructora',
    'description': """
        Módulo de extensiones para Recursos Humanos:
            - Catálogo de Parentescos
            - Beneficiarios en contratos de empleados
            - Asignación de obras a empleados
            - API de descarga de asistencias de checadores (ctrol.asistencias)
        Reportería
           - Reportes de contratos (Temporal, Obra Determinada)
           - Convenio de Confidencialidad
    """,
    'installable': True,
    'application': True,
    'depends': ['hr_payroll', 'hr_contract', 'project', 'project_extra'],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'views/hr_catalogs_views.xml',
        'views/hr_employee_views.xml',
        'views/resource_calendar_views.xml',
        'views/res_config_settings_views.xml',
        'views/ctrol_asistencias_views.xml',
        'report/hr_contract_report.xml',
        'report/report_hr_contract.xml',
        'report/report_convenio_confidencialidad.xml',
    ],
    'external_dependencies': {
        'python': ['jwt'],  # PyJWT
    },
    'auto_install': False,
    'license': 'LGPL-3',
}
