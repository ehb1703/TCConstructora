# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError


class WizardReporteAsistencias(models.TransientModel):
    _name = 'wizard.reporte.asistencias'
    _description = 'Reporte de Asistencia de Checadores'

    employee_ids = fields.Many2many('hr.employee', string='Empleados')
    department_ids = fields.Many2many('hr.department', string='Departamentos')
    job_ids = fields.Many2many('hr.job', string='Puestos')
    project_ids = fields.Many2many('project.project', string='Obras')
    fecha_inicio = fields.Date(string='Fecha inicial', required=True, default=lambda self: fields.Date.today().replace(day=1))
    fecha_fin = fields.Date(string='Fecha final', required=True, default=fields.Date.today)

    def action_generar_excel(self):
        if self.fecha_inicio > self.fecha_fin:
            raise UserError('La fecha inicial no puede ser mayor a la fecha final.')
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/hr_reporte_asistencias?wizard_id=%s' % self.id,
            'target': 'new',
        }
