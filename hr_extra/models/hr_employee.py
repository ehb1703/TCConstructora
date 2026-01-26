# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

class HrEmployeeObra(models.Model):
    _name = 'hr.employee.obra'
    _description = 'Obra asignada a empleado'
    _order = 'employee_id, id'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    project_id = fields.Many2one('project.project', string='Nombre de la obra', required=True)
    etapa_id = fields.Many2one('project.project.stage', string='Etapa', related='project_id.stage_id', readonly=True, store=True)
    fecha_inicio = fields.Date(string='Fecha inicio')
    fecha_fin = fields.Date(string='Fecha fin')

class hrEmployeeInherit(models.Model):
    _inherit = 'hr.employee'

    infonavit = fields.Char(string='Infonavit')
    fonacot = fields.Char(string='Fonacot')
    obra_ids = fields.One2many('hr.employee.obra', 'employee_id', string='Obras asignadas')
    current_project_name = fields.Char(string='Obra Actual', compute='_compute_current_project', store=True, 
        help='Obra vigente del empleado o "Oficina" si no tiene asignación')
    director_ids = fields.Many2many('hr.employee', 'hr_employee_director_rel', 'employee_id', 'director_id', string='Director/Gerente',
        domain="[('job_id.name', 'ilike', 'Director')]")

    @api.onchange('work_contact_id')
    def onchange_name(self):
        if self.work_contact_id:
            self.name = self.work_contact_id.name

    def _prepare_resource_values(self, vals, tz):
        if 'work_contact_id' in vals:
            vals['name'] = vals['legal_name']
        resource_vals = super()._prepare_resource_values(vals, tz)
        return resource_vals

    @api.depends('obra_ids', 'obra_ids.project_id', 'obra_ids.project_id.active', 'obra_ids.fecha_inicio', 'obra_ids.fecha_fin', 'work_location_id')
    def _compute_current_project(self):
        today = date.today()
        
        for emp in self:
            obra_encontrada = False
            if emp.obra_ids:
                obras_vigentes = emp.obra_ids.filtered(lambda o: (o.project_id and o.project_id.active and o.fecha_inicio and o.fecha_fin and
                    o.fecha_inicio <= today <= o.fecha_fin))
                if obras_vigentes:
                    # Tomar la más reciente
                    obra = obras_vigentes.sorted(key=lambda o: o.id, reverse=True)[0]
                    emp.current_project_name = obra.project_id.name
                    obra_encontrada = True
                else:
                    # Si no hay vigentes, buscar obras activas sin validar fechas
                    obras_activas = emp.obra_ids.filtered(lambda o: o.project_id and o.project_id.active)
                    if obras_activas:
                        obra = obras_activas.sorted(key=lambda o: o.id, reverse=True)[0]
                        emp.current_project_name = obra.project_id.name
                        obra_encontrada = True
            
            if not obra_encontrada:
                # Si no tiene obra, usar ubicación de trabajo o "Oficina"
                if emp.work_location_id:
                    emp.current_project_name = emp.work_location_id.name
                else:
                    emp.current_project_name = 'Oficina'


    def get_current_project(self):
        self.ensure_one()
        return self.current_project_name or 'Oficina'

    def get_schedules_for_api(self):
        # Obtiene los horarios del empleado en formato para la API.
        self.ensure_one()
        schedules = []
        if not self.resource_calendar_id:
            return schedules
        
        calendar = self.resource_calendar_id
        tolerance = getattr(calendar, 'tolerance_minutes', 15) or 15
        
        day_mapping = {'0': 'Lunes', '1': 'Martes', '2': 'Miércoles', '3': 'Jueves', '4': 'Viernes', '5': 'Sábado', '6': 'Domingo',}
        
        for attendance in calendar.attendance_ids:
            hour_from = self._decimal_to_time(attendance.hour_from)
            hour_to = self._decimal_to_time(attendance.hour_to)
            schedules.append({
                'day_of_week': day_mapping.get(attendance.dayofweek, attendance.dayofweek),
                'day_of_week_number': int(attendance.dayofweek),
                'hour_from': hour_from,
                'hour_to': hour_to,
                'tolerance_minutes': tolerance,
                'name': attendance.name or '',})
        return schedules


    def _decimal_to_time(self, decimal_hour):
        # Convierte hora decimal a formato HH:MM:SS
        hours = int(decimal_hour)
        minutes = int((decimal_hour - hours) * 60)
        return f"{hours:02d}:{minutes:02d}:00"

    def get_employee_data_for_api(self):
        # Retorna todos los datos del empleado para la API de checadores.
        self.ensure_one()
        contract = self.contract_id or self.env['hr.contract'].search([('employee_id', '=', self.id), ('state', '=', 'open')], limit=1)
        work_entry_type = ''
        if contract and hasattr(contract, 'work_entry_source'):
            work_entry_type = contract.work_entry_source or ''
        
        return {
            'id': self.id,
            'registration_number': self.registration_number or '',
            'full_name': self.name or '',
            'first_name': self.work_contact_id.nombre if self.work_contact_id else '',
            'last_name': self.work_contact_id.apaterno if self.work_contact_id else '',
            'mother_last_name': self.work_contact_id.amaterno if self.work_contact_id else '',
            'department': self.department_id.name if self.department_id else '',
            'job_position': self.job_id.name if self.job_id else '',
            'manager': self.parent_id.name if self.parent_id else '',
            'work_location': self.work_location_id.name if self.work_location_id else '',
            'project': self.current_project_name or 'Oficina',
            'work_entry_type': work_entry_type,
            'schedule_name': self.resource_calendar_id.name if self.resource_calendar_id else '',
            'schedules': self.get_schedules_for_api(),
            'active': self.active,
            'work_email': self.work_email or '',
            'work_phone': self.work_phone or '',
            'mobile_phone': self.mobile_phone or '',}


    @api.model
    def get_employees_for_api(self, filters=None):
        filters = filters or {}
        domain = []
        
        if filters.get('active_only', True):
            domain.append(('active', '=', True))
        
        if filters.get('department_id'):
            domain.append(('department_id', '=', int(filters['department_id'])))
        
        if filters.get('registration_number'):
            domain.append(('registration_number', '=', filters['registration_number']))
        
        if filters.get('with_contract'):
            domain.append(('contract_id', '!=', False))
            domain.append(('contract_id.state', '=', 'open'))
        
        employees = self.search(domain)
        
        result = []
        for emp in employees:
            try:
                result.append(emp.get_employee_data_for_api())
            except Exception as e:
                _logger.error(f"Error obteniendo datos del empleado {emp.id}: {str(e)}")
                continue
        
        return result


class hrContractInherit(models.Model):
    _inherit = 'hr.contract'

    beneficiario_ids = fields.One2many('hr.contract.beneficiario', 'contract_id', string='Beneficiarios')
    total_porcentaje = fields.Integer(string='Total', compute='_compute_total_porcentaje', store=True)
    contract_type_name = fields.Char(string='Tipo de contrato nombre', related='contract_type_id.name', store=False)
    project_id = fields.Many2one('project.project', string='Obra')
    l10n_mx_schedule_pay_temp = fields.Selection(selection=[('daily', 'Diario'), ('weekly', 'Semanal'), ('10_days', '10 Dias'), ('14_days', '14 Dias'), 
        ('bi_weekly', 'Quincenal'), ('monthly', 'Mensual'), ('bi_monthly', 'Bimestral'),], 
        compute='_compute_l10n_mx_schedule_pay', store=True, readonly=False, required=True, string='Pago', default='weekly', index=True)
    daily_wage = fields.Monetary(string='Salario diario', compute='_compute_daily_wage', readonly=True, store=True)

    @api.depends('beneficiario_ids', 'beneficiario_ids.porcentaje')
    def _compute_total_porcentaje(self):
        for contract in self:
            contract.total_porcentaje = sum(contract.beneficiario_ids.mapped('porcentaje'))

    def _compute_daily_wage(self):
        for contract in self:
            if contract.hourly_wage:
                contract.daily_wage = contract.hourly_wage * 8
            if contract.wage:
                if contract.l10n_mx_schedule_pay_temp == 'dialy':
                    contract.daily_wage = contract.wage
                if contract.l10n_mx_schedule_pay_temp == 'weekly':
                    contract.daily_wage = contract.wage / 7
                if contract.l10n_mx_schedule_pay_temp == 'bi_weekly':
                    contract.daily_wage = contract.wage / 15

    @api.constrains('beneficiario_ids')
    def _check_total_porcentaje(self):
        for contract in self:
            total = sum(contract.beneficiario_ids.mapped('porcentaje'))
            if total > 100:
                raise ValidationError(_('El total de porcentajes de beneficiarios no puede exceder el 100%%. Actualmente es %s%%.') % total)

    def action_report_contract(self):
        if self.contract_type_id.name == 'Obra determinada':
            return self.env.ref('hr_extra.action_report_hrcontract_obra').report_action(self)
        else:
            return self.env.ref('hr_extra.action_report_hr_contract').report_action(self)

    def action_report_convenio(self):
        # Genera el convenio de confidencialidad
        return self.env.ref('hr_extra.action_report_convenio_confidencialidad').report_action(self)

    def get_salario_en_letra(self, numero):
        # Convierte número a texto usando función nativa de Odoo
        self.ensure_one()
        if self.company_id:
            currency = self.company_id.currency_id
        else:
            currency = self.env.company.currency_id
        
        entero = int(numero)
        decimal = round(numero - entero, 2)
        salary = currency.amount_to_text(entero).upper()
        if salary == 'UNO PESOS':
            salary = 'UN PESO'
        
        salary = salary.replace('UNO PESOS', 'UN PESOS') + ' ' + str(decimal).split('.')[1] + '/100 M.N.'
        return salary


class HrPayslipWorkedDaysInherit(models.Model):
    _inherit = 'hr.payslip.worked_days'

    @api.depends('is_paid', 'is_credit_time', 'number_of_hours', 'payslip_id', 'contract_id.wage', 'payslip_id.sum_worked_hours')
    def _compute_amount(self):
        for worked_days in self:
            if worked_days.payslip_id.edited or worked_days.payslip_id.state not in ['draft', 'verify']:
                continue
            if not worked_days.contract_id or worked_days.code == 'OUT' or worked_days.is_credit_time:
                worked_days.amount = 0
                continue
            if worked_days.payslip_id.wage_type == "hourly":
                if worked_days.work_entry_type_id.code == 'OVERTIME':
                    worked_days.amount = worked_days.payslip_id.contract_id.hourly_wage * worked_days.number_of_hours if worked_days.is_paid else 0
                else:
                    worked_days.amount = worked_days.payslip_id.contract_id.daily_wage * worked_days.number_of_days if worked_days.is_paid else 0
            else:
                worked_days.amount = worked_days.payslip_id.contract_id.contract_wage * worked_days.number_of_hours / (worked_days.payslip_id._get_regular_worked_hours() or 1) if worked_days.is_paid else 0
