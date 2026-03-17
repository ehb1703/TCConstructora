# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from .hr_employee import _encargado_nomina_extra_domain
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime, timedelta, time
import logging

_logger = logging.getLogger(__name__)

class HrAttendanceOvertimeExtra(models.Model):
    _inherit = 'hr.attendance.overtime'

    attendance_id = fields.Many2one('hr.attendance', string='Asistencia', ondelete='set null', help='Registro hr.attendance relacionado con este overtime')
    reason = fields.Char(string='Razón', help='Motivo del overtime (ej: Retraso en entrada: 01:30)')


class HrLeaveExtra(models.Model):
    _inherit = 'hr.leave'

    disease_ids = fields.One2many('hr.leave.disease', 'leave_id', string='Riesgo de trabajo')

    def action_approve(self, check_state=True):
        vacation_type = self.env['hr.leave.type'].search([('name', '=', 'Vacaciones')])
        if self.holiday_status_id.id == vacation_type.id and self.employee_id.antique == 0:
            raise ValidationError('El empleado no tiene la antigüedad para tomar vacaciones')

        if check_state and any(holiday.state != 'confirm' for holiday in self):
            raise UserError(_('Time off request must be confirmed ("To Approve") in order to approve it.'))

        current_employee = self.env.user.employee_id
        self.filtered(lambda hol: hol.validation_type == 'both').write({'state': 'validate1', 'first_approver_id': current_employee.id})
        self.filtered(lambda hol: hol.validation_type != 'both').action_validate(check_state)
        if not self.env.context.get('leave_fast_create'):
            self.activity_update()

        disease_type = self.env['hr.leave.type'].search([('name', '=', 'Incapacidad por enfermedad (IMSS)')])
        diaanterior = self.request_date_from - timedelta(days=1)
        c = 0
        existe = self.env['hr.leave'].search([('request_date_to','=',diaanterior), ('state','=','validate'), ('holiday_status_id','=',disease_type.id),
            ('employee_id','=',self.employee_id.id)])
        while existe:
            c += existe.number_of_days
            diaanterior = existe.request_date_from - timedelta(days=1)
            existe = self.env['hr.leave'].search([('request_date_to','=',diaanterior), ('state','=','validate'), ('holiday_status_id','=',disease_type.id),
            ('employee_id','=',self.employee_id.id)])
        
        self.env.cr.execute("SELECT t1.d::date d FROM (SELECT * FROM generate_series('" + str(self.request_date_from) + "'::date, '" + str(self.request_date_to) + 
            "'::date, '1 day') as d ORDER BY 1) as t1")
        disease_dates = self.env.cr.dictfetchall()
        disease_lines = []
        for i in disease_dates:
            if i['d'].weekday() != 6:
                if c < 3:
                    percentage = 100
                else:
                    percentage = 60

                c += 1
                self.env.cr.execute('''INSERT INTO hr_leave_disease (CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, LEAVE_ID, EMPLOYEE_ID, DISEASE_DATE, 
                    PERCENTAGE, ACTIVE) VALUES ({}, {}, NOW(), NOW(), {}, {}, '{}', {}, True)'''.format(self.env.user.id, self.env.user.id, self.id, 
                    self.employee_id.id, i['d'], percentage))

        return True


    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        extra = _encargado_nomina_extra_domain(self.env)
        return super()._search(list(domain) + extra if extra else domain, offset=offset, limit=limit, order=order)


class HrAttendanceEncargadoFilter(models.Model):
    _inherit = 'hr.attendance'

    checkout_notes = fields.Char(string='Notas de Salida')

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        extra = _encargado_nomina_extra_domain(self.env)
        return super()._search(list(domain) + extra if extra else domain, offset=offset, limit=limit, order=order)


class HrLeaveDisease(models.Model):
    _name = 'hr.leave.disease'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'leave_id'
    _description = 'Incapacidad por enfermedad'

    leave_id = fields.Many2one('hr.leave', string='Permiso', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado')
    disease_date = fields.Date(string='Fecha')
    percentage = fields.Float(string='Porcentaje')
    active = fields.Boolean(string='Activo', default=True)


class HrLeaveVacations(models.Model):
    _name = 'hr.leave.vacation.days'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Vacaciones según antigüedad'

    numinical = fields.Integer(string='Antiguedad')
    numfinal = fields.Integer(string='Final')
    numdias = fields.Integer(string='Núm. dias')


class HrPayrollHeadcountLine(models.Model):
    _inherit = 'hr.payroll.headcount.line'
    
    department_id = fields.Many2one(related='employee_id.department_id', string='Departamento')
    job_id = fields.Many2one(related='employee_id.job_id', string='Puesto de trabajo')
