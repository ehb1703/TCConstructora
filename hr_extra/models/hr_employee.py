# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from collections import defaultdict, Counter
import pytz
from pytz import timezone
from markupsafe import Markup
from odoo.tools import float_round, date_utils, convert_file, format_amount, float_compare, float_is_zero, plaintext2html
from odoo.tools.safe_eval import safe_eval
from dateutil.relativedelta import relativedelta
from datetime import date, datetime, time
from odoo.osv import expression
import logging

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
    hourly_wage = fields.Float(string='Salario por hora', digits=(10, 2), default=0.0)


class hrEmployeeInherit(models.Model):
    _inherit = 'hr.employee'

    infonavit = fields.Char(string='Infonavit')
    fonacot = fields.Char(string='Fonacot')
    obra_ids = fields.One2many('hr.employee.obra', 'employee_id', string='Obras asignadas')
    current_project_name = fields.Char(string='Obra Actual', compute='_compute_current_project', store=True, 
        help='Obra vigente del empleado o "Oficina" si no tiene asignación')
    director_ids = fields.Many2many('hr.employee', 'hr_employee_director_rel', 'employee_id', 'director_id', string='Director/Gerente',
        domain="[('job_id.name', 'ilike', 'Director'), ('state', '!=', 'baja')]")
    parent_id = fields.Many2one('hr.employee', 'Manager', 
        domain="['|', ('company_id', '=', False), ('company_id', 'in', allowed_company_ids), ('state', '!=', 'baja')]")
    coach_id = fields.Many2one('hr.employee', 'Coach', 
        domain="['|', ('company_id', '=', False), ('company_id', 'in', allowed_company_ids), ('state', '!=', 'baja')]")
    state = fields.Selection(selection=[('activo','Activo'), ('baja','Baja'), ('pensionado','Pensionado'), ('incapacidad','Incapacidad'), 
        ('permiso','Permiso')],
        string='Estado Actual', default='activo', tracking=True)
    empresa_empleadora = fields.Many2one('res.company', string='Empresa empleadora')
    antique = fields.Integer(string='Antigüedad', default=0)

    @api.onchange('work_contact_id')
    def onchange_name(self):
        if self.work_contact_id:
            self.name = self.work_contact_id.name

    def _prepare_resource_values(self, vals, tz):
        if 'work_contact_id' in vals:
            vals['name'] = vals['legal_name']
        resource_vals = super()._prepare_resource_values(vals, tz)
        return resource_vals

    def action_activar_empleado(self):
        self.update({'state': 'activo'})

    def cron_antique(self):
        self.env.cr.execute("""UPDATE hr_employee he SET antique = t2.anios 
            FROM (SELECT t1.employee_id, hc.id, (CASE WHEN (now()::date - hc.date_start) > 365 
                      THEN SPLIT_PART(AGE((CASE WHEN hc.state = 'close' THEN hc.date_end ELSE now()::date END), hc.date_start)::character varying, 'year', 1) 
                      ELSE '0' end)::integer anios
                FROM (SELECT hc.employee_id, MAX(hc.id) id FROM hr_contract hc JOIN hr_contract_type hct ON hc.contract_type_id = hct.id 
                WHERE hc.state != 'cancel' /*AND hct.code = 'Permanent'*/ GROUP BY 1) as t1 JOIN hr_contract hc ON t1.id = hc.id) as t2
            WHERE he.id = t2.employee_id; """)

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
        
        # Obtener foto del empleado (image_1920 es el campo nativo de Odoo)
        photo_base64 = None
        if self.image_1920:
            # image_1920 ya está en base64
            photo_base64 = self.image_1920.decode('utf-8') if isinstance(self.image_1920, bytes) else str(self.image_1920)
        
        # Obtener company: usa empresa_empleadora si está capturada, si no usa company_id del empleado
        company_name = self.empresa_empleadora.name if self.empresa_empleadora else (self.company_id.name if self.company_id else '')
        
        # Asegurar que project nunca esté vacío
        project_name = self.current_project_name or 'Oficina'
        if not project_name or project_name.strip() == '':
            project_name = 'Oficina'
        
        return {
            'id': self.id,
            'registration_number': self.registration_number or '',
            'full_name': self.name or '',
            'first_name': self.work_contact_id.nombre if self.work_contact_id else '',
            'last_name': self.work_contact_id.apaterno if self.work_contact_id else '',
            'mother_last_name': self.work_contact_id.amaterno if self.work_contact_id else '',
            'department': self.department_id.name if self.department_id else '',
            'department_id': self.department_id.id if self.department_id else None,
            'job_position': self.job_id.name if self.job_id else '',
            'job_id': self.job_id.id if self.job_id else None,
            'manager': self.parent_id.name if self.parent_id else '',
            'work_location': self.work_location_id.name if self.work_location_id else '',
            'project': project_name,
            'company': company_name,
            'work_entry_type': work_entry_type,
            'schedule_id': self.resource_calendar_id.id if self.resource_calendar_id else None,
            'schedule_name': self.resource_calendar_id.name if self.resource_calendar_id else '',
            'schedules': self.get_schedules_for_api(),
            'active': self.active,
            'work_email': self.work_email or '',
            'work_phone': self.work_phone or '',
            'mobile_phone': self.mobile_phone or '',
            'photo': photo_base64,  # Foto en base64 (puede ser None si no tiene)
        }


    @api.model
    def get_employees_for_api(self, filters=None):
        """Obtiene empleados para la API con paginación y búsqueda.
        Args:
            filters (dict): Diccionario con filtros opcionales:
                - active_only (bool): Solo empleados activos (default True)
                - department_id (int): Filtrar por departamento
                - registration_number (str): Buscar por número de empleado
                - with_contract (bool): Solo con contrato vigente
                - search (str): Búsqueda por nombre o número de empleado
                - limit (int): Límite de resultados (default 100, max 1000)
                - offset (int): Desplazamiento para paginación (default 0)
        Returns:
            dict: Diccionario con employees, total_count, limit, offset """
        filters = filters or {}
        domain = []
        
        # Filtro de activos
        if filters.get('active_only', True):
            domain.append(('active', '=', True))
        
        # Filtro por departamento
        if filters.get('department_id'):
            domain.append(('department_id', '=', int(filters['department_id'])))
        
        # Filtro por número de registro
        if filters.get('registration_number'):
            domain.append(('registration_number', '=', filters['registration_number']))
        
        # Filtro con contrato
        if filters.get('with_contract'):
            domain.append(('contract_id', '!=', False))
            domain.append(('contract_id.state', '=', 'open'))
        
        # Búsqueda por nombre o número de empleado
        if filters.get('search'):
            search_term = filters['search'].strip()
            search_domain = ['|', '|', '|', ('name', 'ilike', search_term), ('registration_number', 'ilike', search_term), 
                ('work_contact_id.name', 'ilike', search_term), ('work_contact_id.vat', 'ilike', search_term)]
            domain = expression.AND([domain, search_domain])
        
        # Paginación
        limit = int(filters.get('limit', 100))
        offset = int(filters.get('offset', 0))
        
        # Validar límites
        if limit > 1000:
            limit = 1000
        if limit < 1:
            limit = 100
        if offset < 0:
            offset = 0
        
        # Buscar empleados con límite y offset
        employees = self.search(domain, limit=limit, offset=offset, order='id asc')
        
        # Contar total (para paginación)
        total_count = self.search_count(domain)
        
        result = []
        for emp in employees:
            try:
                result.append(emp.get_employee_data_for_api())
            except Exception as e:
                _logger.error(f"Error obteniendo datos del empleado {emp.id}: {str(e)}")
                continue
        
        return {
            'employees': result,
            'total_count': total_count,
            'limit': limit,
            'offset': offset,
            'returned_count': len(result)}


class hrContractInherit(models.Model):
    _inherit = 'hr.contract'

    beneficiario_ids = fields.One2many('hr.contract.beneficiario', 'contract_id', string='Beneficiarios')
    total_porcentaje = fields.Integer(string='Total', compute='_compute_total_porcentaje', store=True)
    contract_type_name = fields.Char(string='Tipo de contrato nombre', related='contract_type_id.name', store=False)
    project_id = fields.Many2one('project.project', string='Obra')
    empresa_contrato_id = fields.Many2one('hr.contract.empresa', string='Empresa para contrato', compute='_compute_empresa_contrato', store=False)
    l10n_mx_schedule_pay_temp = fields.Selection(selection=[('daily', 'Diario'), ('weekly', 'Semanal'), ('10_days', '10 Dias'), ('14_days', '14 Dias'), 
        ('bi_weekly', 'Quincenal'), ('monthly', 'Mensual'), ('bi_monthly', 'Bimestral'),], 
        compute='_compute_l10n_mx_schedule_pay', store=True, readonly=False, required=True, string='Pago', default='weekly', index=True)
    wage_type = fields.Selection([('monthly', 'Fixed Wage'), ('hourly', 'Hourly Wage')], compute='_compute_wage_type', store=True, readonly=True)
    daily_wage = fields.Monetary(string='Salario diario')

    @api.depends('beneficiario_ids', 'beneficiario_ids.porcentaje')
    def _compute_total_porcentaje(self):
        for contract in self:
            contract.total_porcentaje = sum(contract.beneficiario_ids.mapped('porcentaje'))

    @api.onchange('hourly_wage', 'wage')
    def _compute_daily_wage(self):
        for contract in self:
            if contract.hourly_wage:
                salary = contract.hourly_wage * 8
            if contract.wage:
                if contract.l10n_mx_schedule_pay_temp == 'dialy':
                    salary = contract.wage
                if contract.l10n_mx_schedule_pay_temp == 'weekly':
                    salary = contract.wage / 7
                if contract.l10n_mx_schedule_pay_temp == 'bi_weekly':
                    salary = contract.wage / 15
            contract.daily_wage = salary

    @api.constrains('beneficiario_ids')
    def _check_total_porcentaje(self):
        for contract in self:
            total = sum(contract.beneficiario_ids.mapped('porcentaje'))
            if total > 100:
                raise ValidationError(_('El total de porcentajes de beneficiarios no puede exceder el 100%%. Actualmente es %s%%.') % total)

    @api.depends('contract_type_id')
    def _compute_empresa_contrato(self):
        for contract in self:
            empresa = self.env['hr.contract.empresa'].search([('tipo_contrato_id', '=', contract.contract_type_id.id)], limit=1)
            contract.empresa_contrato_id = empresa

    def _get_empresa_contrato(self):
        # Obtiene la empresa configurada para el tipo de contrato actual.
        self.ensure_one()
        empresa = self.env['hr.contract.empresa'].search([('tipo_contrato_id', '=', self.contract_type_id.id)], limit=1)
        return empresa

    def action_report_contract(self):
        tipo = self.contract_type_id.name
        if tipo == 'Obra determinada':
            return self.env.ref('hr_extra.action_report_hrcontract_obra').report_action(self)
        elif tipo == 'Indeterminado':
            return self.env.ref('hr_extra.action_report_hrcontract_indeterminado').report_action(self)
        elif tipo == 'Por periodo de prueba':
            return self.env.ref('hr_extra.action_report_hr_contract_prueba').report_action(self)
        else:
            return self.env.ref('hr_extra.action_report_hr_contract_prueba').report_action(self)

    def action_report_indeterminado_con_convenio(self):
        # Genera contrato indeterminado + convenio de confidencialidad como documentos combinados.
        contrato_action = self.env.ref('hr_extra.action_report_hrcontract_indeterminado').report_action(self)
        return contrato_action

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

    def _preprocess_work_hours_data(self, work_data, date_from, date_to):
        self.env.cr.execute("SELECT COUNT(*) num FROM (SELECT * FROM generate_series('" + str(date_from) + "'::date, '" + str(date_to) + 
            "'::date, '1 day') as d ORDER BY 1) as t1 WHERE NOT EXISTS(SELECT * FROM resource_calendar_attendance rca WHERE rca.calendar_id = " + 
            str(self.resource_calendar_id.id) + " AND rca.dayofweek::integer+1 = EXTRACT(dow from t1.d))")
        descanso = self.env.cr.dictfetchall()
        if descanso[0]['num'] > 0:
            descanso_type = self.env['hr.work.entry.type'].search([('code', '=', 'DESC')])
            work_data[descanso_type.id] = descanso[0]['num'] * 10

        attendance_contracts = self.filtered(lambda c: c.work_entry_source == 'attendance' and c.wage_type == 'hourly')
        overtime_work_entry_type = self.env.ref('hr_work_entry.overtime_work_entry_type', False)
        default_work_entry_type = self.structure_type_id.default_work_entry_type_id

        if not attendance_contracts or not overtime_work_entry_type or len(default_work_entry_type) != 1:
            return

        overtime_hours = self.env['hr.attendance.overtime']._read_group(
            [('employee_id', 'in', self.employee_id.ids), ('date', '>=', date_from), ('date', '<=', date_to)], [], ['duration:sum'],)[0][0]
        unapproved_overtime_hours = round(self.env['hr.attendance'].sudo()._read_group([('employee_id', 'in', self.employee_id.ids), 
            ('check_in', '>=', date_from), ('check_out', '<=', date_to), ('overtime_hours', '>', 0), ('overtime_status', '!=', 'approved')], [], 
            ['overtime_hours:sum'],)[0][0], 2)
        if overtime_hours or overtime_hours > 0:
            work_data[default_work_entry_type.id] -= overtime_hours
            overtime_hours -= unapproved_overtime_hours

        empleados = str(self.employee_id.ids)
        self.env.cr.execute("""SELECT coalesce(sum(hao.duration), 0.0) duration 
            FROM hr_attendance_overtime hao JOIN resource_calendar_leaves rcl ON hao.date = rcl.date_from::date 
            WHERE hao.employee_id IN (""" + empleados[1:-1] + ") AND hao.DATE BETWEEN '" + str(date_from) + "' AND '" + str(date_to) + "'")
        inh_trab = self.env.cr.dictfetchall()
        if inh_trab[0]['duration'] != 0.0:
            overtime_hours -= inh_trab[0]['duration']
            inhabilestrab_type = self.env['hr.work.entry.type'].search([('code', '=', 'FESTTRAB')])
            work_data[inhabilestrab_type.id] = inh_trab[0]['duration']

        self.env.cr.execute("SELECT COUNT(*) num FROM (SELECT * FROM generate_series('" + str(date_from) + "'::date, '" + str(date_to) + 
                """'::date, '1 day') as d ORDER BY 1) as t1 
            WHERE EXISTS(SELECT * FROM resource_calendar_leaves rca WHERE rca.date_from::date = t1.d::date AND rca.holiday_id is null)
            AND NOT EXISTS(SELECT * FROM hr_attendance_overtime hao WHERE hao.DATE = t1.d::date AND hao.employee_id IN (""" + empleados[1:-1] + '))')
        inhabiles = self.env.cr.dictfetchall()
        if inhabiles[0]['num'] > 0:
            inhabil_type = self.env['hr.work.entry.type'].search([('code', '=', 'FESTNOT')])
            work_data[inhabiles_type.id] = inhabiles[0]['num'] * 10

        if overtime_hours > 0:
            work_data[overtime_work_entry_type.id] = overtime_hours

        self.env.cr.execute('''SELECT * FROM hr_leave hl JOIN hr_leave_type hlt ON hl.holiday_status_id = hlt.id AND hlt.name->>'es_MX' = 'Vacaciones' 
            WHERE hl.state = 'validate' AND hl.employee_id IN (''' + empleados[1:-1] + ") AND hl.request_date_from BETWEEN '" + str(date_from) + "' AND '" 
            + str(date_to) + "'")
        prima = self.env.cr.dictfetchall()
        if prima:
            prima_type = self.env['hr.work.entry.type'].search([('code', '=', 'LEAVE120P')])
            work_data[prima_type.id] = prima[0]['number_of_hours']


    def write(self, vals):
        c = 0
        if 'state' in vals or 'project_id' in vals:
            c = 1

        res = super(hrContractInherit, self).write(vals)
        if c == 1 and self.contract_name_type_name == 'Obra determinada':
            obra = self.env['hr.employee.obra'].search([('employee_id', '=', self.employee_id.id), ('project_id', '=', self.project_id.id)])
            if not obra:
                if self.state in ('open', 'close', 'cancel'):
                    self.env['hr.employee.obra'].sudo().create({'employee_id':self.employee_id.id, 'project_id':self.project_id.id, 
                        'fecha_inicio':self.date_start, 'fecha_fin':self.date_end, 'hourly_wage':self.daily_wage/8})
                
            if len(obra) == 1:
                if not obra.fecha_inicio: 
                    obra.write({'fecha_inicio': self.date_start})
                if not obra.hourly_wage:
                    obra.write({'hourly_wage':self.daily_wage/8})
        return res

class HrWorkEntryTypeInherit(models.Model):
    _inherit = 'hr.work.entry.type'

    percentage = fields.Float(string='Porcentaje de aplicación')


class HrPayslipInherit(models.Model):
    _inherit = 'hr.payslip'

    amount = fields.Float(string='Total a pagar', compute='_compute_amount', store=True)

    @api.depends('worked_days_line_ids')
    def _compute_amount(self):
        for payslip in self:
            payslip.amount = sum(payslip.worked_days_line_ids.mapped('amount'))

    @api.depends('contract_id')
    def _compute_daily_salary(self):
        for payslip in self:
            payslip.l10n_mx_daily_salary = payslip.contract_id.daily_wage

    def _get_worked_day_lines_values(self, domain=None):
        self.ensure_one()
        res = []
        hours_per_day = self._get_worked_day_lines_hours_per_day()
        work_hours = self.contract_id.get_work_hours(self.date_from, self.date_to, domain=domain)
        work_hours_ordered = sorted(work_hours.items(), key=lambda x: x[1])
        biggest_work = work_hours_ordered[-1][0] if work_hours_ordered else 0
        add_days_rounding = 0
        for work_entry_type_id, hours in work_hours_ordered:
            work_entry_type = self.env['hr.work.entry.type'].browse(work_entry_type_id)
            days = round(hours / hours_per_day, 5) if hours_per_day else 0
            """if work_entry_type_id == biggest_work:
                days += add_days_rounding """
            day_rounded = self._round_days(work_entry_type, days)
            add_days_rounding += (days - day_rounded)
            attendance_line = {'sequence': work_entry_type.sequence, 'work_entry_type_id': work_entry_type_id, 'number_of_days': day_rounded, 
                'number_of_hours': hours,}
            res.append(attendance_line)
        work_entry_type = self.env['hr.work.entry.type']
        return sorted(res, key=lambda d: work_entry_type.browse(d['work_entry_type_id']).sequence) 


class HrPayslipWorkedDaysInherit(models.Model):
    _inherit = 'hr.payslip.worked_days'

    def _get_costo_hora_por_fecha(self, employee, date_from, date_to):
        if not employee or not date_from or not date_to:
            return None

        obras = employee.obra_ids.filtered(lambda o: o.hourly_wage and o.fecha_inicio and o.fecha_fin)
        if not obras:
            return None

        total_dias = 0
        total_costo = 0.0
        current = date_from
        while current <= date_to:
            obra_dia = obras.filtered(lambda o: o.fecha_inicio <= current <= o.fecha_fin)
            if obra_dia:
                obra = obra_dia.sorted(key=lambda o: o.id, reverse=True)[0]
                total_costo += obra.hourly_wage
                total_dias += 1
            current += relativedelta(days=1)

        if not total_dias:
            return None

        return total_costo / total_dias


    @api.depends('is_paid', 'is_credit_time', 'number_of_hours', 'payslip_id', 'contract_id.wage', 'payslip_id.sum_worked_hours')
    def _compute_amount(self):
        for worked_days in self:
            if worked_days.payslip_id.edited or worked_days.payslip_id.state not in ['draft', 'verify']:
                continue
            if not worked_days.contract_id or worked_days.code == 'OUT' or worked_days.is_credit_time:
                worked_days.amount = 0
                continue
            if worked_days.payslip_id.wage_type == "hourly":
                costo_hora_obra = self._get_costo_hora_por_fecha(worked_days.payslip_id.employee_id, worked_days.payslip_id.date_from, 
                    worked_days.payslip_id.date_to)
                hourly_rate = costo_hora_obra if costo_hora_obra else worked_days.payslip_id.contract_id.hourly_wage
                if costo_hora_obra:
                    daily_rate = hourly_rate * 8
                else:
                    daily_rate = worked_days.payslip_id.contract_id.daily_wage

                if worked_days.work_entry_type_id.code == 'OVERTIME':
                    worked_days.amount = hourly_rate * worked_days.number_of_hours if worked_days.is_paid else 0
                elif worked_days.work_entry_type_id.code == 'DESC':
                    worked_days.amount = daily_rate * worked_days.number_of_days if worked_days.is_paid else 0
                elif worked_days.work_entry_type_id.code == 'FESTTRAB':
                    worked_days.amount = daily_rate * worked_days.number_of_days * 2 if worked_days.is_paid else 0
                elif worked_days.work_entry_type_id.code in ('LEAVE120', 'LEAVE1000', 'LEAVE1100'):
                    worked_days.amount = daily_rate * worked_days.number_of_days
                elif worked_days.work_entry_type_id.code in ('LEAVE120P'):
                    worked_days.amount = daily_rate * worked_days.number_of_days * .25
                elif worked_days.work_entry_type_id.code in ('LEAVE1200'):
                    percentage = self.env['hr.leave.disease'].search([('disease_date','>=',worked_days.payslip_id.date_from), 
                        ('disease_date','<=',worked_days.payslip_id.date_to), ('employee_id','=',worked_days.payslip_id.employee_id.id)])
                    comp = 0
                    parcial = 0
                    amount = 0.0
                    for x in percentage:
                        if x.percentage == 100:
                            comp += 1
                        else:
                            parcial += 1

                    if comp != 0:
                        amount += daily_rate * comp
                    if parcial != 0:
                        amount += daily_rate * parcial * .6

                    worked_days.amount = amount
                else:
                    worked_days.amount = daily_rate * worked_days.number_of_days if worked_days.is_paid else 0
            else:
                worked_days.amount = worked_days.payslip_id.contract_id.contract_wage * worked_days.number_of_hours / (worked_days.payslip_id._get_regular_worked_hours() or 1) if worked_days.is_paid else 0
