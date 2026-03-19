# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.addons.hr_extra.models.hr_employee import _get_encargado_nomina_usuario


class WizardReporteAsistencias(models.TransientModel):
    _name = 'wizard.reporte.asistencias'
    _description = 'Reporte de Asistencia de Checadores'

    employee_ids = fields.Many2many('hr.employee', string='Empleados')
    department_ids = fields.Many2many('hr.department', string='Departamentos')
    job_ids = fields.Many2many('hr.job', string='Puestos')
    project_ids = fields.Many2many('project.project', string='Obras')
    fecha_inicio = fields.Date(string='Fecha inicial', required=True, default=lambda self: fields.Date.today().replace(day=1))
    fecha_fin = fields.Date(string='Fecha final', required=True, default=fields.Date.today)
    tipo_pago = fields.Selection([('semanal', 'Semanal'), ('quincenal', 'Quincenal')],
        string='Tipo de pago', help='Seleccione el tipo de nómina a reportar.')
    mostrar_tipo_pago = fields.Boolean(compute='_compute_mostrar_tipo_pago')

    @api.depends()
    def _compute_mostrar_tipo_pago(self):
        enc = _get_encargado_nomina_usuario(self.env)
        for record in self:
            record.mostrar_tipo_pago = (enc == 'ambas')

    def _get_enc_usuario(self):
        return _get_encargado_nomina_usuario(self.env)

    def action_generar_excel(self):
        if self.fecha_inicio > self.fecha_fin:
            raise UserError('La fecha inicial no puede ser mayor a la fecha final.')

        # Validar permisos: HR Manager, admin o encargado_nomina asignado
        es_admin = self.env.user.has_group('base.group_system')
        es_hr_manager = self.env.user.has_group('hr.group_hr_manager')
        enc = self._get_enc_usuario()

        if not es_admin and not es_hr_manager and not enc:
            raise UserError(
                'No tiene los permisos necesarios para generar este reporte.\n\n'
                'Debe ser Responsable de Recursos Humanos o tener asignado '
                'un valor en el campo "Encargado de Nómina" de su empleado.'
            )

        # Encargado de ambas debe seleccionar tipo de pago
        if enc == 'ambas' and not self.tipo_pago:
            raise UserError(
                'Debe seleccionar el Tipo de pago (Semanal o Quincenal) para generar el reporte.'
            )

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/hr_reporte_asistencias?wizard_id=%s' % self.id,
            'target': 'new',
        }
