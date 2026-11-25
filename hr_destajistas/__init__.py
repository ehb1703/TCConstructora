# -*- coding: utf-8 -*-
from . import models
from . import wizard
from . import controllers

# Dominios originales de las acciones estándar que este módulo ajusta para ocultar destajistas
ACCIONES_ORIGINALES = {
    'hr.open_view_employee_list_my': "[('company_id', 'in', allowed_company_ids)]",
    'hr_attendance.hr_attendance_action': False,
    'hr_attendance.hr_attendance_management_action': "[('check_out', '!=', False)]",
    'hr_attendance.hr_attendance_reporting': False,
    'hr_work_entry.hr_work_entry_action': False,
    'hr_payroll.hr_payslip_action_view_to_pay': "[('state', '=', 'done')]",
    'hr_payroll.action_view_hr_payslip_month_form': False,
    'hr_payroll.hr_work_entry_report_action': "[('company_id', 'in', allowed_company_ids)]",
    'hr_contract.action_hr_contract': "[('employee_id', '!=', False)]",
    'hr_payroll_holidays.hr_leave_work_entry_action': False,
}


def uninstall_hook(env):
    # Sin esto, al desinstalar quedarían menús apuntando al campo tipo_personal, que ya no existiría
    for xmlid, dominio in ACCIONES_ORIGINALES.items():
        accion = env.ref(xmlid, raise_if_not_found=False)
        if accion:
            accion.domain = dominio
