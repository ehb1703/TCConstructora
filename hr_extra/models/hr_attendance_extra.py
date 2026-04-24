# -*- coding: utf-8 -*-
from odoo import api, fields, models, http, _
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
    
    def _get_employee_domain(self):
        domain = [('active','=',True), ('company_id','in',self.env.companies.ids), ('finiquito','=',False),]
        if not self.env.user.has_group('hr_holidays.group_hr_holidays_user'):
            domain += ['|', ('user_id', '=', self.env.uid), ('leave_manager_id', '=', self.env.uid),]

        return domain


    @staticmethod
    def _calcular_dias_habiles(date_from, date_to):
        return sum(1 for n in range((date_to - date_from).days + 1) if (date_from + timedelta(days=n)).weekday() < 5)

    @api.constrains('holiday_status_id', 'request_date_from', 'request_date_to', 'employee_id')
    def _check_maternidad_paternidad_dias(self):
        for leave in self:
            if not leave.holiday_status_id or not leave.request_date_from or not leave.request_date_to:
                continue

            nombre_tipo = (leave.holiday_status_id.name or '').lower()
            es_maternidad = 'maternidad' in nombre_tipo
            es_paternidad = 'paternidad' in nombre_tipo
            if not es_maternidad and not es_paternidad:
                continue

            gender = leave.employee_id.gender if leave.employee_id else False
            dias_habiles = self._calcular_dias_habiles(leave.request_date_from, leave.request_date_to)
            if es_maternidad:
                if gender == 'male':
                    raise ValidationError(_(
                        'El permiso de Maternidad (IMSS) solo puede ser solicitado por empleadas. '
                        'Para empleados masculinos utilice el permiso de Paternidad (IMSS).'))
                if dias_habiles > 90:
                    raise ValidationError(_(
                        'El permiso de Maternidad (IMSS) no puede exceder 90 días hábiles.\n'
                        'Días hábiles solicitados: %d' % dias_habiles))
            elif es_paternidad:
                if gender == 'female':
                    raise ValidationError(_(
                        'El permiso de Paternidad (IMSS) solo puede ser solicitado por empleados masculinos. '
                        'Para empleadas utilice el permiso de Maternidad (IMSS).'))
                if dias_habiles > 5:
                    raise ValidationError(_(
                        'El permiso de Paternidad (IMSS) no puede exceder 5 días hábiles.\n'
                        'Días hábiles solicitados: %d' % dias_habiles))


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
        if self.env.user.login == 'admin':
            return super()._search(domain, offset=offset, limit=limit, order=order)
        extra = _encargado_nomina_extra_domain(self.env)
        return super()._search(list(domain) + extra if extra else domain, offset=offset, limit=limit, order=order)


class HrAttendanceEncargadoFilter(models.Model):
    _inherit = 'hr.attendance'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True, ondelete='cascade', index=True, group_expand='_read_group_employee_id',  
        domain="[('finiquito', '=', False)]")
    checkout_notes = fields.Char(string='Notas de Salida')
    project_id = fields.Many2one('project.project', string='Obra', required=True)
    hourly_wage = fields.Float(string='Salario por hora')

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        if self.env.user.login == 'admin' or http.request.params.get('model') == 'hr.employee':
            return super()._search(domain, offset=offset, limit=limit, order=order)

        if self._context.get('special_display', False):
            full_domain = list(domain)
        else:
            finiquito_domain = [('employee_id.finiquito', '=', False)]
            full_domain = list(domain) + finiquito_domain
        
        extra = _encargado_nomina_extra_domain(self.env)
        if extra:
            full_domain += extra
        return super()._search(full_domain, offset=offset, limit=limit, order=order)


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


class HrLeaveAllocationFiniquitoFilter(models.Model):
    _inherit = 'hr.leave.allocation'

    def _domain_employee_id(self):
        domain = [('company_id', 'in', self.env.companies.ids), ('finiquito','=',False),]
        if not self.env.user.has_group('hr_holidays.group_hr_holidays_user'):
            domain += [('leave_manager_id', '=', self.env.user.id)]

        return domain
