# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api

SABADO, DOMINGO = '5', '6'
FECHA_CAMBIO = '2026-06-23'  # dia en que se agrego el domingo como jornada completa a los horarios de obra


def update_data(cr):
    # T0129: el domingo de los horarios de obra quedo como jornada completa (8:00-18:00), asi Odoo esperaba 10 horas y el domingo trabajado
    # daba tiempo extra negativo (el reporte de asistencias lo mostraba vacio). El domingo se iguala al sabado: lo trabajado despues de las 13:00 es extra.
    env = api.Environment(cr, SUPERUSER_ID, {})
    corregidos = env['resource.calendar']
    for calendario in env['resource.calendar'].with_context(active_test=False).search([('name', 'ilike', 'Obra')]):
        sabado = calendario.attendance_ids.filtered(lambda a: a.dayofweek == SABADO)
        domingo = calendario.attendance_ids.filtered(lambda a: a.dayofweek == DOMINGO)
        if len(sabado) != 1 or len(domingo) != 1:
            continue
        if domingo.hour_to - domingo.hour_from > sabado.hour_to - sabado.hour_from:
            domingo.write({'hour_from': sabado.hour_from, 'hour_to': sabado.hour_to})
            corregidos |= calendario

    if not corregidos:
        return

    # Recalcula el tiempo extra de los domingos trabajados desde el cambio de horario (el mismo calculo de Odoo al registrar la salida)
    empleados = env['hr.employee'].with_context(active_test=False).search([('resource_calendar_id', 'in', corregidos.ids)])
    asistencias = env['hr.attendance'].search([('employee_id', 'in', empleados.ids), ('check_out', '!=', False), ('check_in', '>=', FECHA_CAMBIO)])
    domingos = asistencias.filtered(lambda a: a._get_day_start_and_day(a.employee_id, a.check_in)[1].weekday() == 6)
    if domingos:
        domingos._update_overtime()


def migrate(cr, version):
    if not version:
        return

    update_data(cr)
