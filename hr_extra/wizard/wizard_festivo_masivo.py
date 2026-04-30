# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.hr_extra.models.hr_employee import _encargado_nomina_extra_domain


class WizardFestivoMasivo(models.TransientModel):
    _name = 'hr.festivo.masivo'
    _description = 'Generación masiva de permisos por día festivo no oficial'

    fecha_inicio = fields.Date(string='Fecha de inicio', required=True)
    fecha_fin = fields.Date(string='Fecha de fin', required=True)
    holiday_status_id = fields.Many2one('hr.leave.type', string='Tipo de permiso', required=True, domain=[('requires_allocation', '=', 'no')],)
    department_id = fields.Many2one('hr.department', string='Departamento')
    job_id = fields.Many2one('hr.job', string='Puesto de trabajo')
    employee_ids = fields.Many2many('hr.employee', string='Empleados', compute='_compute_employee_ids', store=False)

    @api.depends('department_id', 'job_id')
    def _compute_employee_ids(self):
        for rec in self:
            domain = [('state', '=', 'activo'), ('finiquito', '=', False)]
            if rec.department_id:
                domain.append(('department_id', '=', rec.department_id.id))
            if rec.job_id:
                domain.append(('job_id', '=', rec.job_id.id))
            
            extra = _encargado_nomina_extra_domain(self.env, 'self')
            if extra:
                domain += extra
            rec.employee_ids = self.env['hr.employee'].search(domain)


    @api.constrains('fecha_inicio', 'fecha_fin')
    def _check_fechas(self):
        for rec in self:
            if rec.fecha_fin < rec.fecha_inicio:
                raise UserError(_('La fecha de fin no puede ser anterior a la fecha de inicio.'))

    def action_generar_permisos(self):
        self.ensure_one()
        if not self.employee_ids:
            raise UserError(_('No hay empleados que coincidan con los filtros seleccionados.'))

        creados = 0
        errores = []
        for emp in self.employee_ids:
            existente = self.env['hr.leave'].search([('employee_id', '=', emp.id), ('holiday_status_id', '=', self.holiday_status_id.id),
                ('date_from', '<=', self.fecha_fin), ('date_to', '>=', self.fecha_inicio), ('state', 'not in', ['refuse']),], limit=1)
            if existente:
                errores.append(emp.name)
                continue
            
            leave = self.env['hr.leave'].sudo().create({'employee_id':emp.id, 'holiday_status_id':self.holiday_status_id.id, 'date_from':self.fecha_inicio,
                'date_to':self.fecha_fin,})
            leave.sudo().action_approve()
            try:
                leave.sudo().action_validate()
            except Exception:
                pass
            
            creados += 1

        msg = _('%s permiso(s) generado(s) correctamente.') % creados
        if errores:
            msg += '\n' + _('Los siguientes empleados ya tenían un permiso en ese período y fueron omitidos:')
            msg += '\n' + ', '.join(errores)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Permisos generados'),
                'message': msg,
                'type': 'success' if not errores else 'warning',
                'sticky': True,}}