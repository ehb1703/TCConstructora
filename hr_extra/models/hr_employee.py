# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from datetime import date, datetime, time
from odoo.osv import expression
import logging
from odoo.tools import (date_utils,)

_logger = logging.getLogger(__name__)


def _get_user_schedule_pay(env):
    """Retorna 'semanal', 'quincenal', o None (sin restricción).
    None si: ADMIN, sin empleado vinculado, encargado_nomina nulo o 'ambas'.
    Si el usuario tiene empleado vinculado con encargado_nomina nulo y pertenece
    a grupos de RRHH/nómina, se restringe a dominio vacío (ve nada) para evitar
    que vea toda la información sin filtro asignado."""
    env.cr.execute('''SELECT 1 FROM res_groups_users_rel rgur JOIN ir_model_data imd ON imd.res_id = rgur.gid
        WHERE rgur.uid = %s AND imd.module = 'base' AND imd.name = 'group_system' LIMIT 1 ''', (env.uid,))
    if env.cr.fetchone():
        return None

    env.cr.execute('''SELECT he.encargado_nomina FROM hr_employee he JOIN resource_resource rr ON rr.id = he.resource_id WHERE rr.user_id = %s
        AND he.active = true LIMIT 1 ''', (env.uid,))
    row = env.cr.fetchone()
    if not row:
        return None

    enc = row[0]
    # encargado_nomina nulo: el usuario tiene empleado pero sin valor asignado
    # → retornar 'none_assigned' para que _encargado_nomina_extra_domain restrinja a vacío
    if not enc:
        return 'none_assigned'
    return None if enc == 'ambas' else enc


def _get_employee_ids_by_schedule(env, enc):
    """IDs de empleados visibles para el encargado de nómina según enc.
    Incluye:
    - Empleados con contrato activo (open/pending) cuyo schedule_pay coincide con enc
    - Empleados SIN ningún contrato (para que el encargado pueda crearles uno)
    - semanal   → schedule_pay = 'weekly'
    - quincenal → schedule_pay IN ('bi-weekly','monthly','bi_monthly','10_days','14_days','daily') """
    if enc == 'semanal':
        schedule_values = ('weekly',)
        placeholders = '%s'
    else:
        schedule_values = ('bi-weekly', 'monthly', 'bi_monthly', '10_days', '14_days', 'daily')
        placeholders = ','.join(['%s'] * len(schedule_values))

    env.cr.execute(f'''SELECT DISTINCT(he.id) FROM hr_employee he WHERE he.active = true
          AND (
              EXISTS (SELECT 1 FROM hr_contract hc WHERE hc.employee_id = he.id AND hc.state IN ('open', 'draft') AND hc.schedule_pay IN ({placeholders}))
              OR NOT EXISTS (SELECT 1 FROM hr_contract hc WHERE hc.employee_id = he.id AND hc.state != 'cancel'))''', schedule_values)
    return [row[0] for row in env.cr.fetchall()]


def _get_encargado_nomina_usuario(env):
    """Retorna el valor de encargado_nomina del empleado vinculado al usuario actual.
    Retorna None si no tiene empleado vinculado o no tiene valor asignado."""
    env.cr.execute('''SELECT he.encargado_nomina FROM hr_employee he JOIN resource_resource rr ON rr.id = he.resource_id
           WHERE rr.user_id = %s AND he.active = true LIMIT 1''', (env.uid,))
    row = env.cr.fetchone()
    return row[0] if row else None

def _get_own_employee_id(env):
    """Retorna el ID del empleado vinculado al usuario actual, o None si no tiene."""
    env.cr.execute('''SELECT he.id FROM hr_employee he JOIN resource_resource rr ON rr.id = he.resource_id
           WHERE rr.user_id = %s AND he.active = true LIMIT 1''', (env.uid,))
    row = env.cr.fetchone()
    return row[0] if row else None

def _encargado_nomina_extra_domain(env, employee_field='employee_id'):
    """Dominio adicional según encargado_nomina del usuario actual.
    Retorna [] si no aplica restricción.
    REGLA: el propio empleado del usuario SIEMPRE es visible, sin importar el enc.
    Esto evita errores de acceso cuando Odoo lee internamente el registro del usuario."""
    enc = _get_user_schedule_pay(env)
    if not enc:
        return []

    # Siempre obtener el propio empleado para incluirlo en cualquier caso
    own_id = _get_own_employee_id(env)
    if enc == 'none_assigned':
        # Sin encargado_nomina asignado → solo ve su propio empleado
        if own_id:
            return [('id', '=', own_id)] if employee_field == 'self' else [(employee_field, '=', own_id)]
        return []

    employee_ids = _get_employee_ids_by_schedule(env, enc)
    # Incluir siempre el propio empleado para evitar errores de acceso internos
    if own_id and own_id not in employee_ids:
        employee_ids = list(employee_ids) + [own_id]

    if not employee_ids:
        return []

    return [('id', 'in', employee_ids)] if employee_field == 'self' else [(employee_field, 'in', employee_ids)]


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

    @api.constrains('fecha_inicio', 'fecha_fin')
    def _chech_end_date(self):
        for record in self:
            obras = self.env['hr.employee.obra'].search([('employee_id', '=', record.employee_id.id), ('fecha_fin', '=', False)])
            if len(obras) > 1:
                raise ValidationError('La fecha final es obligatoria cuando se cambia de obra')

            if record.fecha_inicio and record.fecha_fin and record.fecha_fin < record.fecha_inicio:
                raise ValidationError('La fecha final no puede ser anterior a la fecha de inicio.')


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
    state = fields.Selection(selection=[('activo','Activo'), ('baja','Baja'), ('pensionado','Pensionado'), ('incapacidad','Incapacidad'), ('permiso','Permiso')],
        string='Estado Actual', default='activo', tracking=True)
    finiquito = fields.Boolean(string='Finiquito', default=False, tracking=True)
    empresa_empleadora = fields.Many2one('res.company', string='Empresa empleadora')
    antique = fields.Integer(string='Antigüedad', default=0)
    encargado_nomina = fields.Selection(selection=[('quincenal', 'Quincenal'), ('semanal', 'Semanal'), ('ambas', 'Ambas')],
        string='Encargado de Nómina')
    can_number = fields.Boolean(compute='_compute_can_number')
    hourly_cost = fields.Monetary(string='Salario por hora', currency_field='currency_id', store=True, readonly=True, compute='_compute_salary')
    is_system_user = fields.Boolean(compute='_compute_is_system_user')

    def _compute_is_system_user(self):
        is_admin = self.env.user.has_group('base.group_system')
        for record in self:
            record.is_system_user = is_admin

    def _compute_can_number(self):
        can_edit = self.env['ir.config_parameter'].sudo().get_param('hr.registration_active')
        self.can_number = bool(can_edit)

    @api.depends('obra_ids.hourly_wage')
    def _compute_salary(self):
        cost = 0.00
        c = 0
        for rec in self.obra_ids:
            if rec.hourly_wage > 0:
                c += 1
                cost += rec.hourly_wage
                
        if c != 0:
            self.hourly_cost = cost/c
        else:
            self.hourly_cost = 0


    @api.constrains('l10n_mx_curp')
    def _check_curp(self):
        for record in self:
            if record.l10n_mx_curp and len(record.l10n_mx_curp) != 18:
                raise ValidationError(_('El CURP debe de tener 18 caracteres'))

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
        self.update({'state': 'activo', 'finiquito': False})

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        if self.env.user.name == 'admin':
            return super()._search(domain, offset=offset, limit=limit, order=order)

        crm_bypass_models = ('crm.lead', 'crm.junta.line', 'crm.propuesta.tecnica.revision', 'crm.propuesta.economica.revision')
        if self._context.get('active_model') in crm_bypass_models or self._context.get('default_model') in crm_bypass_models:
            return super()._search(domain, offset=offset, limit=limit, order=order)

        # Lectura directa por ID (Odoo cargando Many2one): no restringir
        if domain and len(domain) == 1 and isinstance(domain[0], (list, tuple)):
            field, op = domain[0][0], domain[0][1]
            if field == 'id' and op in ('=', 'in'):
                return super()._search(domain, offset=offset, limit=limit, order=order)

        if self._context.get('special_display', False):
            extra = []
        else:
            extra = _encargado_nomina_extra_domain(self.env, 'self')

        return super()._search(list(domain) + extra if extra else domain, offset=offset, limit=limit, order=order)


    def _calc_antique_temporal(self, employee_id):
        """Calcula antigüedad en años para empleados con contratos temporales
        (Obra determinada / Por periodo de prueba).
        Reglas:
          - Solo contratos en estado open o close (vencidos y en proceso).
          - Se encadenan ordenados por date_start.
          - Si la brecha entre date_end de un contrato y date_start del siguiente supera 10 días, se reinicia la antigüedad desde ese contrato.
        Retorna años completos (entero). """
        today = date.today()

        self.env.cr.execute('''SELECT hc.date_start, hc.date_end, hc.state
            FROM hr_contract hc JOIN hr_contract_type hct ON hct.id = hc.contract_type_id
            WHERE hc.employee_id = %s AND hc.state IN ('open', 'close') AND hct.code NOT IN ('Permanent')
            ORDER BY hc.date_start ASC ''', (employee_id,))
        rows = self.env.cr.fetchall()
        if not rows:
            return 0

        block_start = rows[-1][0]
        prev_start  = rows[-1][0]
        for date_start, date_end, state in reversed(rows[:-1]):
            c_end = date_end or today
            if (prev_start - c_end).days > 10:
                break
            block_start = date_start
            prev_start  = date_start

        last_date_end, last_state = rows[-1][1], rows[-1][2]
        block_end = last_date_end if last_state == 'close' else today
        return (block_end - block_start).days // 365


    def cron_antique(self):
        # Paso 1: actualizar todos con MAX(id) del contrato más reciente — excluye bajas.
        self.env.cr.execute('''UPDATE hr_employee he SET antique = t2.anios
            FROM (SELECT t1.employee_id, hc.id, (CASE WHEN (now()::date - hc.date_start) > 365 
                        THEN SPLIT_PART(AGE((CASE WHEN hc.state = 'close' THEN hc.date_end ELSE now()::date END),hc.date_start)::character varying, 'year', 1)
                        ELSE '0' END)::integer anios
                FROM (SELECT hc.employee_id, MAX(hc.id) id FROM hr_contract hc JOIN hr_contract_type hct ON hc.contract_type_id = hct.id
                        WHERE hc.state != 'cancel' GROUP BY 1) AS t1 JOIN hr_contract hc ON t1.id = hc.id) AS t2
            WHERE he.id = t2.employee_id AND he.state != 'baja' ''')

        # Paso 2: recalcular temporales aplicando regla de brecha de 10 días.
        self.env.cr.execute("""SELECT DISTINCT hc.employee_id 
            FROM hr_contract hc JOIN hr_contract_type hct ON hct.id = hc.contract_type_id
                                JOIN hr_employee he ON he.id = hc.employee_id
            WHERE hc.id = (SELECT MAX(hc2.id) FROM hr_contract hc2 WHERE hc2.employee_id = hc.employee_id AND hc2.state != 'cancel')
            AND hct.code NOT IN ('Permanent')
            AND he.state != 'baja'""")
        temporal_ids = [r[0] for r in self.env.cr.fetchall()]
        for emp_id in temporal_ids:
            years = self._calc_antique_temporal(emp_id)
            self.env.cr.execute('UPDATE hr_employee SET antique = %s WHERE id = %s AND antique != %s',(years, emp_id, years))


    @api.depends('obra_ids', 'obra_ids.project_id', 'obra_ids.project_id.active', 'obra_ids.fecha_inicio', 'obra_ids.fecha_fin', 'work_location_id')
    def _compute_current_project(self):
        today = date.today()
        for emp in self:
            obra_encontrada = False
            if emp.obra_ids:
                obras_vigentes = emp.obra_ids.filtered(lambda o: o.project_id and o.project_id.active and o.fecha_inicio and o.fecha_fin
                    and o.fecha_inicio <= today <= o.fecha_fin)
                obras_buscar = obras_vigentes or emp.obra_ids.filtered(lambda o: o.project_id and o.project_id.active)
                if obras_buscar:
                    emp.current_project_name = obras_buscar.sorted('id', reverse=True)[0].project_id.name
                    obra_encontrada = True
            
            if not obra_encontrada:
                emp.current_project_name = emp.work_location_id.name if emp.work_location_id else 'OFICINA'


    def get_current_project(self):
        self.ensure_one()
        return self.current_project_name or 'OFICINA'

    def _decimal_to_time(self, decimal_hour):
        hours = int(decimal_hour)
        minutes = int((decimal_hour - hours) * 60)
        return f"{hours:02d}:{minutes:02d}:00"

    def get_schedules_for_api(self):
        self.ensure_one()
        if not self.resource_calendar_id:
            return []
        calendar = self.resource_calendar_id
        tolerance = getattr(calendar, 'tolerance_minutes', 15) or 15
        day_mapping = {'0': 'Lunes', '1': 'Martes', '2': 'Miércoles', '3': 'Jueves', '4': 'Viernes', '5': 'Sábado', '6': 'Domingo'}
        return [{
            'day_of_week': day_mapping.get(att.dayofweek, att.dayofweek),
            'day_of_week_number': int(att.dayofweek),
            'hour_from': self._decimal_to_time(att.hour_from),
            'hour_to': self._decimal_to_time(att.hour_to),
            'tolerance_minutes': tolerance,
            'name': att.name or '',
        } for att in calendar.attendance_ids]

    def get_employee_data_for_api(self):
        self.ensure_one()
        contract = self.contract_id or self.env['hr.contract'].search([('employee_id', '=', self.id), ('state', '=', 'open')], limit=1)
        work_entry_type = (contract.work_entry_source or '') if contract and hasattr(contract, 'work_entry_source') else ''
        photo_base64 = None
        if self.state not in ('baja', 'pensionado') and self.image_1920:
            photo_base64 = self.image_1920.decode('utf-8') if isinstance(self.image_1920, bytes) else str(self.image_1920)
        company = self.empresa_empleadora or self.company_id
        company_name = company.name if company else ''
        company_id = company.id if company else None
        project_name = self.current_project_name or 'OFICINA'
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
            'company_id': company_id,
            'work_entry_type': work_entry_type,
            'schedule_id': self.resource_calendar_id.id if self.resource_calendar_id else None,
            'schedule_name': self.resource_calendar_id.name if self.resource_calendar_id else '',
            'schedules': self.get_schedules_for_api(),
            'active': self.active and self.state not in ('baja', 'pensionado'),
            'work_email': self.work_email or '',
            'work_phone': self.work_phone or '',
            'mobile_phone': self.mobile_phone or '',
            'photo': photo_base64,}

    @api.model
    def get_employees_for_api(self, filters=None):
        filters = filters or {}
        domain = [('active', '=', True)] if filters.get('active_only', True) else []
        if filters.get('department_id'):
            domain.append(('department_id', '=', int(filters['department_id'])))
        if filters.get('registration_number'):
            domain.append(('registration_number', '=', filters['registration_number']))
        if filters.get('with_contract'):
            domain += [('contract_id', '!=', False), ('contract_id.state', '=', 'open')]
        if filters.get('search'):
            term = filters['search'].strip()
            domain = expression.AND([domain, ['|', '|', '|',
                ('name', 'ilike', term), ('registration_number', 'ilike', term),
                ('work_contact_id.name', 'ilike', term), ('work_contact_id.vat', 'ilike', term)]])

        limit = min(max(int(filters.get('limit', 100)), 1), 1000)
        offset = max(int(filters.get('offset', 0)), 0)
        employees = self.search(domain, limit=limit, offset=offset, order='id asc')
        total_count = self.search_count(domain)
        result = []
        for emp in employees:
            try:
                result.append(emp.get_employee_data_for_api())
            except Exception as e:
                _logger.error(f"Error obteniendo datos del empleado {emp.id}: {e}")
        return {'employees': result, 'total_count': total_count,
                'limit': limit, 'offset': offset, 'returned_count': len(result)}

    @api.model_create_multi
    def create(self, vals_list):
        can_edit = self.env['ir.config_parameter'].sudo().get_param('hr.registration_active')
        curp = ''
        rfc = ''
        work_contact = 0
        for vals in vals_list:
            if can_edit:
                seq = self.env['ir.sequence'].next_by_code('numemployee')
                vals['registration_number'] = seq
                vals['identification_id'] = seq
            if 'l10n_mx_curp' in vals:
                curp = vals['l10n_mx_curp']
            if 'l10n_mx_rfc' in vals:
                rfc = vals['l10n_mx_rfc']
            if 'work_contact_id' in vals:
                work_contact = vals['work_contact_id']

        if work_contact == 0:
            raise ValidationError('Es necesario agregar el contacto')

        contact = self.env['res.partner'].search([('id', '=', work_contact)])
        contact.update({'curp': curp, 'vat': rfc})
        res = super(hrEmployeeInherit, self).create(vals_list)
        return res


    def write(self, vals):
        c = 0
        if 'l10n_mx_curp' in vals:
            c = 1
            curp = vals['l10n_mx_curp']
        else:
            curp = self.l10n_mx_curp

        if 'l10n_mx_rfc' in vals:
            c = 1
            rfc = vals['l10n_mx_rfc']
        else:
            rfc = self.l10n_mx_rfc
        
        if c != 0:
            work_contact = 0
            if 'work_contact_id' in vals:
                work_contact = vals['work_contact_id']
            else:
                work_contact = self.work_contact_id.id

            if work_contact == 0:
                raise ValidationError('Es necesario agregar el contacto')

            if not self.env.context.get('syncing_info'):
                contact = self.env['res.partner'].search([('id', '=', work_contact)])
                contact.with_context(syncing_info=True).update({'curp': curp, 'vat': rfc})

        res = super(hrEmployeeInherit, self).write(vals)
        """if self.hourly_cost == 0.00:
            raise ValidationError('Es necesario capturar el salario diario en obras') """
        return res


class hrContractInherit(models.Model):
    _inherit = 'hr.contract'

    beneficiario_ids = fields.One2many('hr.contract.beneficiario', 'contract_id', string='Beneficiarios')
    total_porcentaje = fields.Integer(string='Total', compute='_compute_total_porcentaje', store=True)
    contract_type_name = fields.Char(string='Tipo de contrato nombre', related='contract_type_id.name', store=False)
    project_id = fields.Many2one('project.project', string='Obra')
    empresa_contrato_id = fields.Many2one('hr.contract.empresa', string='Empresa para contrato', compute='_compute_empresa_contrato', store=False)
    wage_type = fields.Selection([('monthly', 'Fixed Wage'), ('hourly', 'Hourly Wage')], compute='_compute_wage_type', store=True, readonly=True)
    daily_wage = fields.Monetary(string='Salario diario')
    work_entry_source = fields.Selection(selection=[('calendar', 'Horario de trabajo'), ('attendance', 'Asistencia'),],
        default='attendance')

    @api.depends('beneficiario_ids.porcentaje')
    def _compute_total_porcentaje(self):
        for contract in self:
            contract.total_porcentaje = sum(contract.beneficiario_ids.mapped('porcentaje'))

    @api.onchange('hourly_wage', 'wage')
    def _compute_daily_wage(self):
        for contract in self:
            salary = 0
            if contract.hourly_wage:
                salary = contract.hourly_wage * 8
            elif contract.wage:
                divisor = {'daily': 1, 'weekly': 7, 'bi-weekly': 15}.get(contract.schedule_pay)
                if divisor:
                    salary = contract.wage / divisor
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
            contract.empresa_contrato_id = self.env['hr.contract.empresa'].search([('tipo_contrato_id', '=', contract.contract_type_id.id)], limit=1)

    def _get_empresa_contrato(self):
        self.ensure_one()
        return self.env['hr.contract.empresa'].search([('tipo_contrato_id', '=', self.contract_type_id.id)], limit=1)

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
        return self.env.ref('hr_extra.action_report_hrcontract_indeterminado').report_action(self)

    def action_report_convenio(self):
        return self.env.ref('hr_extra.action_report_convenio_confidencialidad').report_action(self)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        if self.env.user.name == 'admin':
            return super()._search(domain, offset=offset, limit=limit, order=order)
        extra = _encargado_nomina_extra_domain(self.env)
        return super()._search(list(domain) + extra if extra else domain, offset=offset, limit=limit, order=order)

    def get_salario_en_letra(self, numero):
        self.ensure_one()
        currency = self.company_id.currency_id if self.company_id else self.env.company.currency_id
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

        overtime_hours = self.env['hr.attendance.overtime']._read_group([('employee_id', 'in', self.employee_id.ids), ('date', '>=', date_from), 
            ('date', '<=', date_to)], [], ['duration:sum'],)[0][0]
        unapproved_overtime_hours = round(self.env['hr.attendance'].sudo()._read_group([('employee_id', 'in', self.employee_id.ids), 
            ('check_in', '>=', date_from), ('check_out', '<=', date_to), ('overtime_hours', '>', 0), ('overtime_status', '!=', 'approved')], [], 
            ['overtime_hours:sum'],)[0][0], 2)

        if overtime_hours or overtime_hours > 0:
            work_data[default_work_entry_type.id] -= overtime_hours
            overtime_hours -= unapproved_overtime_hours

        empleados = str(self.employee_id.ids)
        if self.schedule_pay != 'weekly':
            if date_to.date().strftime('%d') == '31':
                self.env.cr.execute("""SELECT coalesce(sum(hao.duration), 0.0) duration 
                    FROM hr_work_entry hao WHERE hao.employee_id IN (""" + empleados[1:-1] + ") AND hao.DATE_START::DATE = '" + str(date_to) + "'::DATE ")
                out_day = self.env.cr.dictfetchall()
                if out_day[0]['duration'] > 0:
                    work_data[default_work_entry_type.id] -= out_day[0]['duration']

            if date_to.date().strftime('%d') == '28':
                work_data[default_work_entry_type.id] += 20

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
            work_data[inhabil_type.id] = inhabiles[0]['num'] * 10

        if overtime_hours != 0:
            work_data[overtime_work_entry_type.id] = overtime_hours

        self.env.cr.execute('''SELECT * FROM hr_leave hl JOIN hr_leave_type hlt ON hl.holiday_status_id = hlt.id AND hlt.name->>'es_MX' = 'Vacaciones' 
            WHERE hl.state = 'validate' AND hl.employee_id IN (''' + empleados[1:-1] + ") AND hl.request_date_from BETWEEN '" + str(date_from) + "' AND '" 
            + str(date_to) + "'")
        prima = self.env.cr.dictfetchall()
        if prima:
            prima_type = self.env['hr.work.entry.type'].search([('code', '=', 'LEAVE120P')])
            work_data[prima_type.id] = prima[0]['number_of_hours']


    @api.model_create_multi
    def create(self, vals_list):
        salario = self.env['hr.salario.minimo'].get_salario_vigente()
        for vals in vals_list:
            if salario and not vals.get('hourly_wage'):
                vals['hourly_wage'] = salario.salario_hora
                vals['daily_wage'] = salario.salario_hora * 8
        return super(hrContractInherit, self).create(vals_list)

    @api.onchange('contract_type_id', 'employee_id')
    def _onchange_set_salario_minimo(self):
        try:
            if not self.hourly_wage:
                salario = self.env['hr.salario.minimo'].get_salario_vigente()
                if salario:
                    self.hourly_wage = salario.salario_hora
        except Exception:
            pass

    def write(self, vals):
        c = 0
        if 'state' in vals or 'project_id' in vals:
            c = 1

        res = super(hrContractInherit, self).write(vals)
        if c == 1 and self.contract_type_name == 'Obra determinada':
            if self.project_id:
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


    def _get_more_vals_attendance_interval(self, interval):
        result = super()._get_more_vals_attendance_interval(interval)
        result.append(('project_id', interval[2].project_id.id))
        result.append(('hourly_wage', interval[2].hourly_wage))
        return result


class HrWorkEntryTypeInherit(models.Model):
    _inherit = 'hr.work.entry.type'

    percentage = fields.Float(string='Porcentaje de aplicación')


class HrPayslipInherit(models.Model):
    _inherit = 'hr.payslip'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True,
        domain="[('finiquito', '=', False), '|', ('company_id', '=', False), ('company_id', '=', company_id), '|', ('active', '=', True), ('active', '=', False)]")
    amount = fields.Float(string='Total a pagar', compute='_compute_amount', store=True)

    @api.depends('worked_days_line_ids.amount')
    def _compute_amount(self):
        for payslip in self:
            payslip.amount = sum(payslip.worked_days_line_ids.mapped('amount'))

    @api.depends('contract_id')
    def _compute_daily_salary(self):
        for payslip in self:
            cost = payslip.employee_id.hourly_cost
            payslip.l10n_mx_daily_salary = cost * 8

    def _get_worked_day_lines_values(self, domain=None):
        self.ensure_one()
        hours_per_day = self._get_worked_day_lines_hours_per_day()
        work_hours = self.contract_id.get_work_hours(self.date_from, self.date_to, domain=domain)
        work_hours_ordered = sorted(work_hours.items(), key=lambda x: x[1])
        add_days_rounding = 0
        res = []
        for work_entry_type_id, hours in work_hours_ordered:
            work_entry_type = self.env['hr.work.entry.type'].browse(work_entry_type_id)
            days = round(hours / hours_per_day, 5) if hours_per_day else 0
            day_rounded = self._round_days(work_entry_type, days)
            add_days_rounding += (days - day_rounded)
            attendance_line = {'sequence': work_entry_type.sequence, 'work_entry_type_id': work_entry_type_id, 'number_of_days': day_rounded, 
                'number_of_hours': hours,}
            res.append(attendance_line)

        work_entry_type = self.env['hr.work.entry.type']
        return sorted(res, key=lambda d: work_entry_type.browse(d['work_entry_type_id']).sequence) 


    @api.depends('date_from', 'date_to', 'struct_id')
    def _compute_warning_message(self):
        for slip in self:
            slip.warning_message = False
            if not slip.date_from or not slip.date_to:
                continue
            warnings = []
            if slip.contract_id and (slip.date_from < slip.contract_id.date_start
                    or (slip.contract_id.date_end and slip.date_to > slip.contract_id.date_end)):
                warnings.append(_('El período seleccionado no coincide con el período de validez del contrato.'))

            if slip.date_to > date_utils.end_of(fields.Date.today(), 'month'):
                warnings.append(_(
                    'Es posible que no se generen entradas de trabajo para el período comprendido entre %(start)s a %(end)s.',
                    start=date_utils.add(date_utils.end_of(fields.Date.today(), 'month'), days=1),
                    end=slip.date_to,))

            if (slip.contract_id.schedule_pay or slip.contract_id.structure_type_id.default_schedule_pay)\
                    and slip.date_from + slip._get_schedule_timedelta() != slip.date_to:
                warnings.append(_('La duración de un recibo de nómina no es exacta según el tipo de estructura.'))

            inconsistencia = self.env['hr.attendance'].search([('employee_id', '=', slip.employee_id.id), ('check_in', '>=', slip.date_from), 
                ('check_in', '<=', slip.date_to), ('worked_hours', '>', 16)])
            if len(inconsistencia) > 0:
                warnings.append(_('Existen asistencias inconsistentes en el periodo'))

            if warnings:
                warnings = [_('Este recibo de nómina puede estar incorrecto: ')] + warnings
                slip.warning_message = "\n  ・ ".join(warnings)


    def compute_sheet(self):
        payslips = self.filtered(lambda slip: slip.state in ['draft', 'verify'])
        for payslip in payslips:
            if payslip.warning_message:
                raise ValidationError('Existen inconsistencias en el recibo, favor de resolver antes de continuar con el proceso')
        
        self.calculate_project()
        return super().compute_sheet()


    def calculate_project(self):
        attendance = self._get_attendance_by_payslip()[self]
        salary = sum(x.amount for x in self.worked_days_line_ids)
        self.env.cr.execute('''SELECT project_id, hourly_wage, SUM(worked_hours - overtime_hours) horas, SUM(overtime_hours) extra, MIN(check_in::DATE) fecha
            FROM hr_attendance ha WHERE id in (''' + str(attendance.ids).replace('[', '').replace(']', '') + ") GROUP BY 1, 2 ORDER BY 3 DESC, 5 DESC")
        project = self.env.cr.dictfetchall()
        num = len(project)
        if num == 1:
            existe = self.env['hr.payslip.project'].search([('payslip_id', '=', self.id), ('project_id', '=', project[0]['project_id'])])
            if existe:
                if salary != existe.importe:
                    existe.write({'importe': salary})
            else:
                self.env['hr.payslip.project'].create({'payslip_id':self.id, 'project_id':project[0]['project_id'], 'importe':salary})
        else:
            c = 1
            total = 0
            for x in project:
                if c == num:
                    sal = salary - total
                else:
                    sal = 0.0
                    dias = int(x['horas'] / 10)
                    if x['extra'] != 0.0:
                        sal += x['extra'] * x['hourly_wage']
                    if dias > 0:
                        sal += dias * x['hourly_wage'] * 8
                    total += sal
                
                c += 1
                existe = self.env['hr.payslip.project'].search([('payslip_id', '=', self.id), ('project_id', '=', x['project_id'])])
                if existe:
                    if sal != existe.importe:
                        existe.write({'importe': sal})
                else:
                    self.env['hr.payslip.project'].create({'payslip_id':self.id, 'project_id':x['project_id'], 'importe':sal})


    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        if self.env.su:
            return super()._search(domain, offset=offset, limit=limit, order=order)
        extra = _encargado_nomina_extra_domain(self.env)
        return super()._search(list(domain) + extra if extra else domain, offset=offset, limit=limit, order=order)


class HrWorkEntryEncargadoFilter(models.Model):
    _inherit = 'hr.work.entry'

    project_id = fields.Many2one('project.project', string='Obra', required=True)
    hourly_wage = fields.Float(string='Salario por hora')

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        if self.env.su:
            return super()._search(domain, offset=offset, limit=limit, order=order)
        extra = _encargado_nomina_extra_domain(self.env)
        return super()._search(list(domain) + extra if extra else domain, offset=offset, limit=limit, order=order)


class HrPayslipWorkedDaysInherit(models.Model):
    _inherit = 'hr.payslip.worked_days'

    def _get_costo_hora_por_fecha(self, employee, date_from, date_to):
        if not employee or not date_from or not date_to:
            return None

        obras = employee.obra_ids.filtered(lambda o: o.hourly_wage and o.fecha_inicio)
        if not obras:
            return None

        total_dias = 0
        total_costo = 0.0
        current = date_from
        while current <= date_to:
            obra_dia = obras.filtered(lambda o: o.fecha_inicio <= current)
            if obra_dia:
                obra = obra_dia.sorted(key=lambda o: o.id, reverse=True)[0]
                total_costo += obra.hourly_wage
                total_dias += 1
            current += relativedelta(days=1)
        return (total_costo / total_dias) if total_dias else None


    @api.depends('is_paid', 'is_credit_time', 'number_of_hours', 'payslip_id', 'contract_id.wage', 'payslip_id.sum_worked_hours')
    def _compute_amount(self):
        for worked_days in self:
            if worked_days.payslip_id.edited or worked_days.payslip_id.state not in ['draft', 'verify']:
                continue
            if not worked_days.contract_id or worked_days.code == 'OUT' or worked_days.is_credit_time:
                worked_days.amount = 0
                continue
            if worked_days.payslip_id.wage_type == 'hourly':
                costo_hora_obra = self._get_costo_hora_por_fecha(worked_days.payslip_id.employee_id, worked_days.payslip_id.date_from, 
                    worked_days.payslip_id.date_to)
                hourly_rate = costo_hora_obra if costo_hora_obra else worked_days.payslip_id.contract_id.hourly_wage
                if costo_hora_obra:
                    daily_rate = hourly_rate * 8
                else:
                    daily_rate = worked_days.payslip_id.contract_id.daily_wage

                #Horas extras
                if worked_days.work_entry_type_id.code == 'OVERTIME':
                    worked_days.amount = hourly_rate * worked_days.number_of_hours if worked_days.is_paid else 0
                #Domingos
                elif worked_days.work_entry_type_id.code == 'DESC':
                    worked_days.amount = daily_rate * worked_days.number_of_days if worked_days.is_paid else 0
                #Festivos trabajados
                elif worked_days.work_entry_type_id.code == 'FESTTRAB':
                    worked_days.amount = daily_rate * worked_days.number_of_days * 2 if worked_days.is_paid else 0
                elif worked_days.work_entry_type_id.code in ('LEAVE120', 'LEAVE1000', 'LEAVE1100', 'PATERNIDAD'):
                    worked_days.amount = daily_rate * worked_days.number_of_days
                elif worked_days.work_entry_type_id.code in ('LEAVE120P'):
                    worked_days.amount = daily_rate * worked_days.number_of_days * .25
                elif worked_days.work_entry_type_id.code in ('LEAVE90'):
                    worked_days.amount = 0
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
