# -*- coding: utf-8 -*-
{
    'name': 'Payroll Extra',
    'category': 'Human Resources/Payroll',
    'sequence': 290,
    'summary': 'Manage your employee payroll records',
    'installable': True,
    'application': True,
    'depends': ['hr_payroll'],
    'data': [
        'views/hr_employee_views.xml',
        'report/hr_contract_report.xml',
        'report/report_hr_contract.xml',
    ],
    'license': 'OEEL-1',
}
