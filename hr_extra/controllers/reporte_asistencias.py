# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.hr_extra.models.hr_employee import (_encargado_nomina_extra_domain, _get_encargado_nomina_usuario, _get_employee_ids_by_schedule,)
from datetime import datetime, time
import io
import xlsxwriter
import pytz


class ControllerReporteAsistencias(http.Controller):

    @http.route('/web/binary/hr_reporte_asistencias', type='http', auth='user')
    def hr_reporte_asistencias(self, wizard_id, **kw):
        wizard = request.env['wizard.reporte.asistencias'].sudo().browse(int(wizard_id))
        if not wizard.exists():
            return request.not_found()

        fecha_inicio = wizard.fecha_inicio
        fecha_fin    = wizard.fecha_fin
        tz = pytz.timezone('America/Mexico_City')
        dt_inicio = tz.localize(datetime.combine(fecha_inicio, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        dt_fin    = tz.localize(datetime.combine(fecha_fin,    time.max)).astimezone(pytz.utc).replace(tzinfo=None)
        domain = [('check_in', '>=', dt_inicio), ('check_in', '<=', dt_fin)]
        if wizard.employee_ids:
            domain.append(('employee_id', 'in', wizard.employee_ids.ids))
        if wizard.department_ids:
            domain.append(('employee_id.department_id', 'in', wizard.department_ids.ids))
        if wizard.job_ids:
            domain.append(('employee_id.job_id', 'in', wizard.job_ids.ids))
        if wizard.project_ids:
            emp_ids_obra = request.env['hr.employee.obra'].sudo().search([
                ('project_id', 'in', wizard.project_ids.ids)
            ]).mapped('employee_id').ids
            domain.append(('employee_id', 'in', emp_ids_obra if emp_ids_obra else [-1]))

        # Restricción por encargado_nomina:
        # - semanal/quincenal: filtro automático por schedule_pay
        # - ambas + tipo_pago elegido: filtrar por el tipo_pago seleccionado en el wizard
        # - admin/HR manager sin enc: sin restricción adicional
        enc = _get_encargado_nomina_usuario(request.env)
        if enc == 'ambas' and wizard.tipo_pago:
            emp_ids = _get_employee_ids_by_schedule(request.env, wizard.tipo_pago)
            if emp_ids:
                domain.append(('employee_id', 'in', emp_ids))
            else:
                domain.append(('employee_id', 'in', [-1]))
        else:
            extra = _encargado_nomina_extra_domain(request.env)
            if extra:
                domain += extra

        attendances = request.env['hr.attendance'].sudo().search(domain)
        attendances = attendances.sorted(key=lambda a: (a.employee_id.current_project_name or '', a.employee_id.name or '', a.check_in or datetime.min,))
        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output)
        ws = wb.add_worksheet('Asistencias')

        fmt_titulo = wb.add_format({'font_name': 'Arial', 'font_size': 14, 'bold': 1, 'valign': 'vcenter', 'align': 'center',})
        fmt_periodo = wb.add_format({'font_name': 'Arial', 'font_size': 11, 'bold': 1, 'valign': 'vcenter', 'align': 'center',})
        fmt_encabezado = wb.add_format({'font_name': 'Arial', 'font_size': 11, 'bold': 1, 'valign': 'vcenter', 'align': 'center', 
            'top': 1, 'bottom': 1, 'left': 1, 'right': 1, 'bg_color': '#D9D9D9',})
        fmt_normal = wb.add_format({'font_name': 'Arial', 'font_size': 10, 'valign': 'vcenter', 'align': 'left', 'top': 1, 'bottom': 1, 'left': 1, 'right': 1})
        fmt_centro = wb.add_format({'font_name': 'Arial', 'font_size': 10, 'valign': 'vcenter', 'align': 'center', 'top': 1, 'bottom': 1, 'left': 1, 'right': 1})

        # Anchos columnas — se agrega col I para Tipo de Pago
        for col, ancho in enumerate([35, 25, 25, 30, 15, 18, 18, 15, 15]):
            ws.set_column(col, col, ancho)

        ws.set_row(0, 22)
        ws.set_row(1, 18)
        ws.set_row(2, 18)

        # Etiqueta de tipo de pago para título
        tipo_label = ''
        if enc == 'ambas' and wizard.tipo_pago:
            tipo_label = ' — ' + dict([('semanal', 'Semanal'), ('quincenal', 'Quincenal')]).get(wizard.tipo_pago, '')

        # Fila 1: Título
        ws.merge_range(0, 0, 0, 8, 'Reporte de asistencia de personal' + tipo_label, fmt_titulo)
        # Fila 2: Periodo
        ws.merge_range(1, 0, 1, 8,
            'Periodo %s - %s' % (fecha_inicio.strftime('%d/%m/%Y'), fecha_fin.strftime('%d/%m/%Y')),
            fmt_periodo)

        # Fila 3: Encabezados
        for col, nombre in enumerate(['Nombre', 'Departamento', 'Puesto', 'Obra', 'Fecha', 'Hora de Entrada', 'Hora de Salida', 'Tiempo Extra', 'Tipo de Pago']):
            ws.write(2, col, nombre, fmt_encabezado)

        # Datos
        fila = 3
        for att in attendances:
            emp = att.employee_id
            check_in_local  = pytz.utc.localize(att.check_in ).astimezone(tz) if att.check_in  else None
            check_out_local = pytz.utc.localize(att.check_out).astimezone(tz) if att.check_out else None
            overtime = request.env['hr.attendance.overtime'].sudo().search([('employee_id', '=', emp.id), 
                ('date', '=', att.check_in.date() if att.check_in else False)], limit=1)
            tiempo_extra = ''
            if overtime and overtime.duration and overtime.duration > 0:
                horas   = int(overtime.duration)
                minutos = int((overtime.duration - horas) * 60)
                tiempo_extra = '%02d:%02d' % (horas, minutos)

            # Tipo de pago del empleado desde su contrato activo
            contrato = request.env['hr.contract'].sudo().search([('employee_id', '=', emp.id), ('state', '=', 'open')], limit=1)
            tipo_pago_emp = ''
            if contrato and contrato.schedule_pay:
                tipo_pago_emp = 'Semanal' if contrato.schedule_pay == 'weekly' else 'Quincenal'

            ws.write(fila, 0, emp.name or '', fmt_normal)
            ws.write(fila, 1, emp.department_id.name if emp.department_id else '', fmt_centro)
            ws.write(fila, 2, emp.job_id.name if emp.job_id else '', fmt_centro)
            ws.write(fila, 3, emp.current_project_name or '', fmt_centro)
            ws.write(fila, 4, check_in_local.strftime('%d/%m/%Y') if check_in_local else '', fmt_centro)
            ws.write(fila, 5, check_in_local.strftime('%H:%M') if check_in_local else '', fmt_centro)
            ws.write(fila, 6, check_out_local.strftime('%H:%M') if check_out_local else '', fmt_centro)
            ws.write(fila, 7, tiempo_extra, fmt_centro)
            ws.write(fila, 8, tipo_pago_emp, fmt_centro)
            ws.set_row(fila, 15)
            fila += 1

        wb.close()
        content = output.getvalue()
        output.close()

        return request.make_response(content, [('Content-Type', 'application/octet-stream'), 
            ('Content-Disposition', 'attachment; filename=Reporte_Asistencias_%s_%s.xlsx;' % (fecha_inicio.strftime('%Y%m%d'), fecha_fin.strftime('%Y%m%d'))),])
