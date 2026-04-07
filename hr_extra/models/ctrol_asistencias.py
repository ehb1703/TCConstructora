# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging
from datetime import datetime, timedelta
import pytz

_logger = logging.getLogger(__name__)


class CtrolAsistencias(models.Model):
    _name = 'ctrol.asistencias'
    _description = 'Control de Asistencias - Tabla Intermedia para Checadores'
    _order = 'check_date desc, id desc'
    _rec_name = 'id'

    employee_id = fields.Integer(string='ID Empleado', help='Número de empleado desde el checador')
    registration_number = fields.Char(string='Número de Empleado', index=True, 
        help='Número de empleado desde el checador (identificador principal)')
    check_type = fields.Selection([('entrada', 'Entrada'), ('salida', 'Salida') ], string='Tipo de Registro', required=True, default='entrada')
    status = fields.Selection([('success', 'Exitoso'), ('error', 'Error')], string='Estado del Registro', default='success', required=True,
       help='Indica si el registro se procesó correctamente o tiene errores')
    observaciones = fields.Text(string='Observaciones', help='Descripción de errores o advertencias del registro')
    photo_url = fields.Char(string='URL Fotografía', help='URL de la foto tomada en el checador' )
    latitude = fields.Float(string='Latitud', digits=(10, 8), help='Coordenada GPS - Latitud')
    longitude = fields.Float(string='Longitud', digits=(11, 8), help='Coordenada GPS - Longitud')
    # check_date almacena la hora LOCAL del checador convertida a UTC para que Odoo la gestione correctamente.
    # La hora original del checador se preserva en check_date_local (solo lectura, para auditoría).
    check_date = fields.Datetime(string='Fecha de Registro', required=True, help='Fecha y hora del registro (UTC)')
    check_date_local = fields.Char(string='Hora Local Checador', readonly=True,
        help='Hora original enviada por el checador en su zona horaria local (solo auditoría)')
    log_status = fields.Selection([('pendiente', 'Pendiente'), ('error', 'Error'), ('importada', 'Importada'), ('fallido', 'Fallido')], 
        string='Estado', default='pendiente', required=True)
    lateness_time = fields.Char(string='Tiempo de Retraso', help='Formato HH:MM - Ejemplo: 07:15')
    left_early_time = fields.Char(string='Salida Anticipada', help='Formato HH:MM - Ejemplo: 00:30')
    is_active = fields.Boolean(string='Activo', default=True)
    createdAt = fields.Datetime(string='Fecha Creación', help='Fecha de creación en formato aaaa/mm/dd hh:mm', default=fields.Datetime.now)
    updatedAt = fields.Datetime(string='Fecha Actualización', help='Fecha de actualización en formato aaaa/mm/dd hh:mm', default=fields.Datetime.now)
    verification_status = fields.Selection([('auto', 'Automático'), ('manual_review', 'Revisión Manual'), ('approved', 'Aprobado'), ('rejected', 'Rechazado')], 
        string='Estado de Verificación')
    match_percentage = fields.Integer(string='Porcentaje de Coincidencia', help='Porcentaje de coincidencia biométrica (0-100)')
    log_message = fields.Text(string='Mensaje de Log', help='Mensaje o descripción del registro')
    attendance_id = fields.Many2one('hr.attendance', string='Asistencia Generada', ondelete='set null',
        help='Registro hr.attendance generado al importar esta asistencia. Permite trazar directamente el origen del registro.')
    sigob_log_folio = fields.Char(string='Folio Log SIGOB')
    user_valid_id = fields.Integer(string='ID Usuario Validador')
    date_validated = fields.Datetime(string='Fecha de Validación')
    employee_name = fields.Char(string='Nombre Empleado', compute='_compute_employee_name', store=True)
    is_system_user = fields.Boolean(compute='_compute_is_system_user')

    def _compute_is_system_user(self):
        is_admin = (self.env.user.has_group('base.group_system') or self.env.user.has_group('base.group_erp_manager'))
        for record in self:
            record.is_system_user = is_admin

    @api.depends('registration_number', 'employee_id')
    def _compute_employee_name(self):
        for record in self:
            employee = False
            if record.registration_number:
                employee = self.env['hr.employee'].sudo().search([('registration_number', '=', record.registration_number)], limit=1)
            if not employee and record.employee_id:
                employee = self.env['hr.employee'].sudo().search([('id', '=', record.employee_id)], limit=1)
            if employee:
                record.employee_name = employee.name
                if not record.employee_id:
                    record.employee_id = employee.id
            else:
                record.employee_name = f'Empleado #{record.registration_number or record.employee_id}'
    

    @api.constrains('latitude')
    def _check_latitude(self):
        for record in self:
            if record.latitude and (record.latitude < -90 or record.latitude > 90):
                raise ValidationError(_('La latitud debe estar entre -90 y 90 grados.'))
    
    @api.constrains('longitude')
    def _check_longitude(self):
        for record in self:
            if record.longitude and (record.longitude < -180 or record.longitude > 180):
                raise ValidationError(_('La longitud debe estar entre -180 y 180 grados.'))
    
    @api.constrains('match_percentage')
    def _check_match_percentage(self):
        for record in self:
            if record.match_percentage and (record.match_percentage < 0 or record.match_percentage > 100):
                raise ValidationError(_('El porcentaje de coincidencia debe estar entre 0 y 100.'))
    
    def write(self, vals):
        vals['updatedAt'] = fields.Datetime.now()
        return super(CtrolAsistencias, self).write(vals)
    
    def to_json(self):
        self.ensure_one()
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'registration_number': self.registration_number or '',
            'employee_name': self.employee_name,
            'check_type': self.check_type,
            'photo_url': self.photo_url or '',
            'latitude': self.latitude,
            'longitude': self.longitude,
            'check_date': self.check_date.strftime('%Y-%m-%d %H:%M:%S') if self.check_date else '',
            'log_status': self.log_status,
            'status': self.status,
            'observaciones': self.observaciones or '',
            'lateness_time': self.lateness_time or '',
            'left_early_time': self.left_early_time or '',
            'is_active': self.is_active,
            'createdAt': self.createdAt.strftime('%Y/%m/%d %H:%M:%S') if self.createdAt else '',
            'updatedAt': self.updatedAt.strftime('%Y/%m/%d %H:%M:%S') if self.updatedAt else '',
            'verification_status': self.verification_status or '',
            'match_percentage': self.match_percentage or 0,
            'log_message': self.log_message or '',
            'attendance_id': self.attendance_id.id if self.attendance_id else None,
            'sigob_log_folio': self.sigob_log_folio or '',
            'user_valid_id': self.user_valid_id or 0,
            'date_validated': self.date_validated.strftime('%Y-%m-%d %H:%M:%S') if self.date_validated else ''}
    
    @api.model
    def _local_to_utc(self, local_dt, tz_name):
        # Convierte un datetime naive (hora local del checador) a UTC naive para almacenar en Odoo.
        try:
            tz = pytz.timezone(tz_name)
            local_aware = tz.localize(local_dt, is_dst=None)
        except pytz.exceptions.AmbiguousTimeError:
            tz = pytz.timezone(tz_name)
            local_aware = tz.localize(local_dt, is_dst=False)
        return local_aware.astimezone(pytz.utc).replace(tzinfo=None)

    @api.model
    def _get_checador_tz(self):
        # Obtiene la zona horaria configurada para el usuario api_checadores.
        ICP = self.env['ir.config_parameter'].sudo()
        username = ICP.get_param('api_checadores.username', '')
        if username:
            user = self.env['res.users'].sudo().search([('login', '=', username)], limit=1)
            if user and user.tz:
                return user.tz
        # Fallback: zona horaria de la compañía
        company_tz = self.env.company.resource_calendar_id.tz if self.env.company.resource_calendar_id else ''
        if company_tz:
            return company_tz
        return 'America/Mexico_City'

    @api.model
    def create_from_checador(self, vals):
        """Crea un registro desde el checador validando datos.
        Convierte la hora local del checador a UTC para almacenamiento correcto en Odoo.
        Preserva la hora original en check_date_local para auditoría."""
        if vals.get('registration_number') and not vals.get('employee_id'):
            employee = self.env['hr.employee'].sudo().search([('registration_number', '=', vals['registration_number'])], limit=1)
            if employee:
                vals['employee_id'] = employee.id
        
        # Parsear check_date como hora LOCAL del checador
        raw_date = vals.get('check_date', '')
        if raw_date:
            date_str = str(raw_date).replace('T', ' ').replace('Z', '')
            if '.' in date_str:
                date_str = date_str.split('.')[0]
            try:
                local_dt = datetime.strptime(date_str.strip(), '%Y-%m-%d %H:%M:%S')
            except ValueError:
                local_dt = datetime.strptime(date_str.strip(), '%Y-%m-%d %H:%M')
            
            # Guardar la hora original del checador para auditoría
            vals['check_date_local'] = local_dt.strftime('%Y-%m-%d %H:%M:%S')
            # Convertir hora local → UTC para almacenamiento en Odoo
            tz_name = self._get_checador_tz()
            utc_dt = self._local_to_utc(local_dt, tz_name)
            vals['check_date'] = utc_dt.strftime('%Y-%m-%d %H:%M:%S')
            _logger.info(f"Checador TZ={tz_name} | Local={local_dt} → UTC={utc_dt}")
        
        record = self.create(vals)
        _logger.info(f"Asistencia creada en ctrol.asistencias - ID: {record.id}, "
                    f"Registration#: {vals.get('registration_number')}, "
                    f"Tipo: {vals.get('check_type')}, Check_date_local: {vals.get('check_date_local')}, "
                    f"Check_date_utc: {vals.get('check_date')}, "
                    f"Status: {vals.get('status', 'success')}")
        return record
    

    @staticmethod
    def _convert_time_to_hours(time_str):
        # Convertir horas
        if not time_str or not isinstance(time_str, str):
            return 0.0
        
        try:
            time_str = time_str.strip()
            if ':' not in time_str:
                return 0.0
            
            parts = time_str.split(':')
            if len(parts) != 2:
                return 0.0
            
            hours = int(parts[0])
            minutes = int(parts[1])
            if hours < 0 or minutes < 0 or minutes >= 60:
                return 0.0
            
            return hours + (minutes / 60.0)
        except (ValueError, AttributeError):
            return 0.0


    def _get_employee_from_registration(self):
        self.ensure_one()
        if self.registration_number:
            employee = self.env['hr.employee'].sudo().search([('registration_number', '=', self.registration_number)], limit=1)
            return employee if employee else False
        else:
            return False
    
    def _validate_for_import(self):
        """ Valida que el registro pueda importarse a Odoo. 
            1. employee_id existe en hr.employee
            2. Empleado tiene contrato activo (state='open')
            3. check_date no es nulo y formato correcto
            4. check_type está en {entrada, salida} """
        self.ensure_one()
        employee = self._get_employee_from_registration()
        if not employee:
            return (False, f'Empleado no encontrado | Registration: {self.registration_number}')
        contract = self.env['hr.contract'].sudo().search(
            [('employee_id', '=', employee.id), ('state', '=', 'open')], limit=1)
        if not contract:
            return (False, f'Sin contrato activo | Empleado: {employee.name} | Registration: {self.registration_number}')
        if not self.check_date:
            return (False, 'Formato de fecha inválido | check_date es nulo')
        if not isinstance(self.check_date, datetime):
            return (False, f'Formato de fecha inválido | check_date debe ser datetime, recibido: {type(self.check_date)}')
        if self.check_type not in ['entrada', 'salida']:
            return (False, f'check_type inválido | Valor recibido: "{self.check_type}" | Valores permitidos: entrada, salida')
        
        return (True, '')

    def action_reenviar_a_pendiente(self):
        """Regresa registros con log_status='error' a 'pendiente' para reintento.
        Funciona desde el formulario (registro individual) y desde la lista (selección múltiple)."""
        errores = self.filtered(lambda r: r.log_status == 'error')
        if not errores:
            raise ValidationError(_('No hay registros en estado Error seleccionados.'))
        errores.write({'log_status':'pendiente', 'log_message':False, 'attendance_id':False,})
        _logger.info(f'Reenviados a pendiente: {len(errores)} registro(s) | IDs: {errores.ids}')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reenviados a Pendiente'),
                'message': _('%d registro(s) marcados como Pendiente para reintento.') % len(errores),
                'type': 'success',
                'sticky': False,},}
    
    def _map_to_attendance(self):
        """Mapea el registro a hr.attendance usando zona horaria local del checador.

        check_date está en UTC. El día laboral se determina con check_date_local (hora original del checador). El rango UTC del día local se usa para buscar
        duplicados en hr.attendance (que también guarda en UTC).

        REGLAS:
        1. Solo UNA entrada por día laboral por empleado
        2. Solo UNA salida por día laboral por empleado
        3. Si no hay salida de un día anterior, no bloquea el siguiente día """
        self.ensure_one()
        employee = self._get_employee_from_registration()
        if not employee:
            return (False, f'Empleado no encontrado | Registration: {self.registration_number}')

        # Determinar la hora local del checador para calcular el día laboral correcto
        if self.check_date_local:
            try:
                local_dt = datetime.strptime(self.check_date_local, '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                local_dt = self.check_date
        else:
            tz_name = self._get_checador_tz()
            try:
                tz = pytz.timezone(tz_name)
                utc_aware = pytz.utc.localize(self.check_date)
                local_dt = utc_aware.astimezone(tz).replace(tzinfo=None)
            except Exception:
                local_dt = self.check_date

        current_date = local_dt.date()

        # Calcular rango UTC del día laboral local para buscar en hr.attendance
        tz_name = self._get_checador_tz()
        try:
            tz = pytz.timezone(tz_name)
            day_start_utc = tz.localize(datetime.combine(current_date, datetime.min.time())).astimezone(pytz.utc).replace(tzinfo=None)
            day_end_utc = tz.localize(datetime.combine(current_date, datetime.max.time().replace(microsecond=0))).astimezone(pytz.utc).replace(tzinfo=None)
        except Exception:
            day_start_utc = datetime.combine(current_date, datetime.min.time())
            day_end_utc = datetime.combine(current_date, datetime.max.time().replace(microsecond=0))

        check_date_utc = self.check_date
        AttendanceModel = self.env['hr.attendance'].sudo()
        if self.check_type == 'entrada':
            entrada_del_dia = AttendanceModel.search([('employee_id', '=', employee.id), ('check_in', '>=', day_start_utc), ('check_in', '<=', day_end_utc)], 
                limit=1)
            if entrada_del_dia:
                return (False, f'Ya existe entrada del día {current_date} | Attendance ID: {entrada_del_dia.id} | Check-in: {entrada_del_dia.check_in}')

            # Cerrar entradas abiertas de días ANTERIORES para evitar solapamiento en hr.attendance.
            # Si el empleado no fichó salida en un día previo, se cierra automáticamente con check_out = 1 segundo antes del nuevo check_in. No afecta el día actual.
            open_prev = AttendanceModel.search([('employee_id', '=', employee.id), ('check_out', '=', False), ('check_in', '<', day_start_utc)], 
                order='check_in desc')
            auto_closed = 0
            for prev in open_prev:
                auto_checkout = check_date_utc - timedelta(seconds=1)
                prev.write({'check_out': auto_checkout,
                    'checkout_notes': f'Cierre automático - sin salida registrada en checador (entrada siguiente: {local_dt})',})
                auto_closed += 1

            self.env.cr.execute('SELECT min(project_id) project, min(hourly_wage) wage FROM hr_employee_obra WHERE employee_id = ' + str(employee.id) + 
                    " AND ('" + str(self.check_date_local) + "'::date BETWEEN fecha_inicio AND '" + str(self.check_date_local) + 
                    "'::date OR fecha_inicio is null)")
            rows = self.env.cr.fetchall()
            if rows[0][0] == None:
                return (False, f'No existe registro de salario | Registration: {self.registration_number}')

            try:
                attendance = AttendanceModel.create({'employee_id':employee.id, 'check_in':check_date_utc, 'in_latitude':self.latitude or 0.0,
                    'in_longitude':self.longitude or 0.0, 'project_id':rows[0][0], 'hourly_wage':rows[0][1],})
                auto_msg = f' (se cerraron {auto_closed} entrada(s) previa(s) sin salida)' if auto_closed else ''
                return (attendance, f'Entrada registrada | Attendance ID: {attendance.id} | Check-in local: {local_dt}{auto_msg}')
            except Exception as e:
                return (False, f'Error al crear entrada | Error: {str(e)}')

        elif self.check_type == 'salida':
            """ Busca duplicado de salida verificando que el check_in también pertenezca al día laboral actual. Sin esta condición, un attendance de un día 
            anterior (con check_in fuera del rango) podría coincidir por check_out si su salida real cae dentro del rango UTC del día actual,
            generando un falso positivo de duplicado."""
            salida_del_dia = AttendanceModel.search([('employee_id', '=', employee.id), ('check_out', '>=', day_start_utc), ('check_out', '<=', day_end_utc),
                ('check_in', '>=', day_start_utc),], limit=1)
            if salida_del_dia:
                return (False, f'Ya existe salida del día {current_date} | Attendance ID: {salida_del_dia.id} | Check-out: {salida_del_dia.check_out}')

            open_attendance = AttendanceModel.search([('employee_id', '=', employee.id), ('check_out', '=', False), ('check_in', '<=', check_date_utc)], 
                order='check_in desc', limit=1)
            if not open_attendance:
                return (False, f'Salida sin entrada previa | Employee: {employee.name} | Fecha local: {local_dt}')
            if check_date_utc <= open_attendance.check_in:
                return (False, f'Salida debe ser posterior a entrada | Check-in: {open_attendance.check_in} | Check-out intentado: {check_date_utc}')
            try:
                open_attendance.write({'check_out': check_date_utc, 'out_latitude': self.latitude or 0.0, 'out_longitude': self.longitude or 0.0,})
                worked_hours = open_attendance.worked_hours
                return (open_attendance, f'Salida registrada | Attendance ID: {open_attendance.id} | Horas trabajadas: {worked_hours:.2f}')
            except Exception as e:
                return (False, f'Error al registrar salida | Error: {str(e)}')

        return (False, f'check_type inválido | Valor: {self.check_type}')
    

    def _get_threshold_hours(self, employee):
        # Obtiene el umbral de tolerancia en horas desde configuración o horario del empleado.
        threshold_hours = 15 / 60.0  # fallback 15 min
        if employee.resource_calendar_id:
            cal_tolerance = getattr(employee.resource_calendar_id, 'tolerance_minutes', None)
            if cal_tolerance is not None and cal_tolerance >= 0:
                threshold_hours = cal_tolerance / 60.0
        else:
            company = employee.company_id or self.env.company
            threshold_minutes = getattr(company, 'overtime_company_threshold', None)
            if threshold_minutes is not None and threshold_minutes >= 0:
                threshold_hours = threshold_minutes / 60.0
                _logger.info(f'T0051: Umbral desde config empresa: {threshold_minutes} min')
        return threshold_hours

        # CASO 2: Salida anticipada — registrar siempre si viene del checador
        if self.left_early_time:
            early_hours = self._convert_time_to_hours(self.left_early_time)
            if early_hours > threshold_hours:
                try:
                    we_vals = {'employee_id': employee.id, 'name': f'Salida anticipada {self.left_early_time} - {attendance.check_in.date()}',
                        'date_start': attendance.check_out, 'date_stop': attendance.check_out + timedelta(hours=early_hours),
                        'work_entry_type_id': overtime_type.id if overtime_type else False, 'state': 'draft',}
                    if contract:
                        we_vals['contract_id'] = contract.id
                    we = WorkEntryModel.create(we_vals)
                    messages.append(f'Salida anticipada | WE ID: {we.id} | -{self.left_early_time}')
                    _logger.info(f'T0051: Salida anticipada | {employee.name} | -{self.left_early_time}')
                except Exception as e:
                    _logger.error(f'T0051: Error WE salida anticipada: {str(e)}')

        if messages:
            return (True, ' | '.join(messages))
        if scheduled_hours > 0:
            return (False, f'Sin horas extra ni anticipada | Trabajadas: {worked_hours:.2f}h / Programadas: {scheduled_hours:.2f}h')
        if self.left_early_time:
            threshold_min = round(threshold_hours * 60)
            return (False, f'left_early_time ({self.left_early_time}) no supera umbral ({threshold_min} min)')
        return (False, 'Sin horas extra ni salida anticipada que registrar')

    
    @api.model
    def process_pending_logs(self):
        start_time = datetime.now()
        pending_records = self.search([('log_status', '=', 'pendiente')], order='check_date asc, id asc')
        total_records = len(pending_records)
        if total_records == 0:
            return {'total_procesados': 0, 'exitosos': 0, 'errores': 0, 'detalles_errores': [], 'tiempo_ejecucion': '0 segundos'}
        
        exitosos = 0
        errores = 0
        detalles_errores = []
        for record in pending_records:
            try:
                # 2.1 VALIDACIÓN
                is_valid, validation_message = record._validate_for_import()
                if not is_valid:
                    record.write({'log_status': 'error', 'log_message': validation_message})
                    errores += 1
                    detalles_errores.append({'id': record.id, 'employee': record.registration_number, 'error': validation_message})
                    continue
                
                # 2.2 MAPEO A hr.attendance
                attendance, attendance_message = record._map_to_attendance()
                if not attendance:
                    record.write({'log_status': 'error', 'log_message': attendance_message })
                    errores += 1
                    detalles_errores.append({'id': record.id, 'employee': record.registration_number, 'error': attendance_message})
                    continue
                
                messages = [attendance_message]
                # 2.5 ACTUALIZACIÓN DE ESTADO: Marcar como importada
                final_message = ' | '.join(messages)
                write_vals = {'log_status': 'importada', 'log_message': final_message}
                # Guardar referencia al attendance generado para trazabilidad rápida
                if attendance and hasattr(attendance, 'id'):
                    write_vals['attendance_id'] = attendance.id
                record.write(write_vals)
                exitosos += 1
                _logger.info(f"Registro procesado exitosamente: {final_message}")
            
            except Exception as e:
                # Capturar cualquier error no controlado
                error_msg = f'Error inesperado durante procesamiento | Error: {str(e)}'
                record.write({'log_status': 'error', 'log_message': error_msg})
                errores += 1
                detalles_errores.append({'id': record.id, 'employee': record.registration_number, 'error': error_msg})
                _logger.error(f"Error inesperado en registro {record.id}: {str(e)}", exc_info=True)
        
        # 3. ESTADÍSTICAS FINALES
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        result = {'total_procesados': total_records, 'exitosos': exitosos, 'errores': errores, 'detalles_errores': detalles_errores, 
            'tiempo_ejecucion': f'{execution_time:.2f} segundos'}
        return result

    
    @api.model
    def get_import_statistics(self):
        # Obtiene estadísticas de importación para dashboard/reportes.
        today = datetime.now().date()
        
        # Contadores por estado
        pendientes = self.search_count([('log_status', '=', 'pendiente')])
        importadas_hoy = self.search_count([('log_status', '=', 'importada'), ('updatedAt', '>=', datetime.combine(today, datetime.min.time()))])
        errores_hoy = self.search_count([('log_status', '=', 'error'), ('updatedAt', '>=', datetime.combine(today, datetime.min.time()))])
        
        total_hoy = importadas_hoy + errores_hoy
        tasa_exito = (importadas_hoy / total_hoy * 100) if total_hoy > 0 else 0
        
        # Último procesamiento
        ultimo_importado = self.search([('log_status', '=', 'importada')], order='updatedAt desc', limit=1)
        ultimo_procesamiento = ultimo_importado.updatedAt if ultimo_importado else False
        
        # Empleados con errores recurrentes
        errores_recurrentes = self.read_group([('log_status', '=', 'error')], ['registration_number'], ['registration_number'])
        
        return {'pendientes': pendientes, 'importadas_hoy': importadas_hoy, 'errores_hoy': errores_hoy, 'tasa_exito': round(tasa_exito, 2),
            'ultimo_procesamiento': ultimo_procesamiento, 'empleados_con_errores': len(errores_recurrentes)}
