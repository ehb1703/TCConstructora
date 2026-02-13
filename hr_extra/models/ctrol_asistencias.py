# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class CtrolAsistencias(models.Model):
    _name = 'ctrol.asistencias'
    _description = 'Control de Asistencias - Tabla Intermedia para Checadores'
    _order = 'check_date desc, id desc'
    _rec_name = 'id'

    # Campos según documento T0040
    employee_id = fields.Integer(string='ID Empleado', required=True, help='Número de empleado desde el checador')
    registration_number = fields.Char(string='Número de Empleado', required=True, index=True, 
        help='Número de empleado desde el checador (identificador principal)')
    check_type = fields.Selection([('entrada', 'Entrada'), ('salida', 'Salida') ], string='Tipo de Registro', required=True, default='entrada')
    # Campos para manejo de errores (T0049)
    status = fields.Selection([('success', 'Exitoso'), ('error', 'Error')], string='Estado del Registro', default='success', required=True,
       help='Indica si el registro se procesó correctamente o tiene errores')
    observaciones = fields.Text(string='Observaciones', help='Descripción de errores o advertencias del registro')
    photo_url = fields.Char(string='URL Fotografía', help='URL de la foto tomada en el checador' )
    latitude = fields.Float(string='Latitud', digits=(10, 8), help='Coordenada GPS - Latitud')
    longitude = fields.Float(string='Longitud', digits=(11, 8), help='Coordenada GPS - Longitud')
    check_date = fields.Datetime(string='Fecha de Registro', required=True, help='Fecha y hora del registro en formato aaaa-mm-dd hh:mm')    
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
    
    @api.depends('registration_number', 'employee_id')
    def _compute_employee_name(self):
        for record in self:
            employee = False
            
            # Intentar buscar por registration_number primero
            if record.registration_number:
                employee = self.env['hr.employee'].sudo().search([
                    ('registration_number', '=', record.registration_number)
                ], limit=1)
            
            # Fallback: buscar por employee_id (legacy)
            if not employee and record.employee_id:
                employee = self.env['hr.employee'].sudo().search([
                    ('id', '=', record.employee_id)
                ], limit=1)
            
            if employee:
                record.employee_name = employee.name
                # Sincronizar employee_id si no existe
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
    def create_from_checador(self, vals):
        """Crea un registro desde el checador validando datos.
        
        Busca el employee_id usando el registration_number si no viene en vals. """
        # Buscar employee_id usando registration_number
        if vals.get('registration_number') and not vals.get('employee_id'):
            employee = self.env['hr.employee'].sudo().search([
                ('registration_number', '=', vals['registration_number'])
            ], limit=1)
            if employee:
                vals['employee_id'] = employee.id
        
        # Convertir check_date si viene en formato ISO con T
        if vals.get('check_date') and 'T' in str(vals.get('check_date')):
            vals['check_date'] = str(vals['check_date']).replace('T', ' ')
        
        # Crear registro
        record = self.create(vals)
        _logger.info(f"Asistencia creada en ctrol.asistencias - ID: {record.id}, "
                    f"Registration#: {vals.get('registration_number')}, "
                    f"Tipo: {vals.get('check_type')}, Status: {vals.get('status', 'success')}")
        
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
        # Busca el empleado usando registration_number.
        self.ensure_one()
        if self.registration_number:
            employee = self.env['hr.employee'].sudo().search([('registration_number', '=', self.registration_number)], limit=1)
            return employee if employee else False
        else:
            return False
    
    def _validate_for_import(self):
        """ Valida que el registro pueda importarse a Odoo. 
            1. employee_id existe en hr.employee
            2. check_date no es nulo y formato correcto
            3. check_type está en {entrada, salida} """
        self.ensure_one()
        
        employee = self._get_employee_from_registration()
        if not employee:
            return (False, f'Empleado no encontrado | Registration: {self.registration_number}')
        if not self.check_date:
            return (False, 'Formato de fecha inválido | check_date es nulo')
        if not isinstance(self.check_date, datetime):
            return (False, f'Formato de fecha inválido | check_date debe ser datetime, recibido: {type(self.check_date)}')
        if self.check_type not in ['entrada', 'salida']:
            return (False, f'check_type inválido | Valor recibido: "{self.check_type}" | Valores permitidos: entrada, salida')
        
        return (True, '')

    
    def _map_to_attendance(self):
        """ Mapea el registro a hr.attendance.
            - Si check_type='entrada': Crea nuevo hr.attendance con check_in + coordenadas GPS entrada
            - Si check_type='salida': Busca attendance abierto y actualiza check_out + coordenadas GPS salida """
        self.ensure_one()        
        employee = self._get_employee_from_registration()
        if not employee:
            return (False, f'Empleado no encontrado | Registration: {self.registration_number}')
        
        AttendanceModel = self.env['hr.attendance'].sudo()        
        if self.check_type == 'entrada':
            open_attendance = AttendanceModel.search([('employee_id', '=', employee.id), ('check_out', '=', False)], limit=1)
            if open_attendance:
                # Verificar si la entrada abierta es del MISMO día que la nueva
                open_date = open_attendance.check_in.date() if open_attendance.check_in else None
                new_date = self.check_date.date() if self.check_date else None

                if open_date and new_date and open_date == new_date:
                    # Mismo día: es una entrada duplicada real → error
                    return (False, f'Entrada ya existe | Attendance ID: {open_attendance.id} | Fecha: {open_attendance.check_in}')
                else:
                    # Día distinto: hay una entrada vieja sin cerrar → cerrar automáticamente
                    # Se cierra con el mismo check_in (0 horas trabajadas) para no bloquear la nueva entrada
                    _logger.warning(
                        f'T0051: Entrada abierta de día anterior detectada | '
                        f'Attendance ID: {open_attendance.id} | Fecha antigua: {open_attendance.check_in} | '
                        f'Cerrando automáticamente para crear nueva entrada del {new_date}'
                    )
                    open_attendance.write({'check_out': open_attendance.check_in})
            
            try:
                attendance = AttendanceModel.create({
                    'employee_id': employee.id,
                    'check_in': self.check_date,
                    'in_latitude': self.latitude or 0.0,
                    'in_longitude': self.longitude or 0.0,
                })
                return (attendance, f'Entrada registrada | Attendance ID: {attendance.id} | Check-in: {self.check_date}')
            except Exception as e:
                return (False, f'Error al crear entrada | Error: {str(e)}')
        elif self.check_type == 'salida':
            # Buscar entrada previa sin salida
            open_attendance = AttendanceModel.search([('employee_id', '=', employee.id), ('check_out', '=', False), ('check_in', '<=', self.check_date)], 
                order='check_in desc', limit=1)
            
            if not open_attendance:
                return (False, f'Salida sin entrada previa | Employee: {employee.name} | Fecha: {self.check_date}')
            if self.check_date <= open_attendance.check_in:
                return (False, f'Salida debe ser posterior a entrada | Check-in: {open_attendance.check_in} | Check-out intentado: {self.check_date}')
            
            try:
                open_attendance.write({
                    'check_out': self.check_date,
                    'out_latitude': self.latitude or 0.0,
                    'out_longitude': self.longitude or 0.0,
                })
                # worked_hours se calcula automáticamente en hr.attendance
                worked_hours = open_attendance.worked_hours
                return (open_attendance, f'Salida registrada | Attendance ID: {open_attendance.id} | Horas trabajadas: {worked_hours:.2f}')
            except Exception as e:
                return (False, f'Error al registrar salida | Error: {str(e)}')
        
        return (False, f'check_type inválido | Valor: {self.check_type}')
    

    def _map_to_overtime(self, attendance_id):
        # Crea registro de hora extra/retraso si lateness_time > umbral.
        self.ensure_one()
        if not self.lateness_time:
            return (False, 'No hay lateness_time registrado')
        
        # Buscar empleado primero (necesario para obtener su compañía y horario)
        employee = self._get_employee_from_registration()
        if not employee:
            return (False, 'Empleado no encontrado')
        
        # Obtener umbral desde configuración de Asistencias (NO del parámetro attendance_lateness_threshold)
        threshold_hours = 15 / 60.0  # fallback
        try:
            company = employee.company_id or self.env.company
            threshold_minutes = getattr(company, 'overtime_company_threshold', None)
            if threshold_minutes is not None and threshold_minutes >= 0:
                threshold_hours = threshold_minutes / 60.0
                _logger.info(f'T0051: Umbral desde Asistencias → Configuración: {threshold_minutes} min')
            elif employee.resource_calendar_id:
                cal_tolerance = getattr(employee.resource_calendar_id, 'tolerance_minutes', None)
                if cal_tolerance is not None and cal_tolerance >= 0:
                    threshold_hours = cal_tolerance / 60.0
                    _logger.info(f'T0051: Umbral desde horario {employee.resource_calendar_id.name}: {cal_tolerance} min')
        except Exception as e:
            _logger.warning(f'T0051: No se pudo obtener umbral, usando 15 min: {str(e)}')
        
        # Convertir lateness_time a horas y comparar
        lateness_hours = self._convert_time_to_hours(self.lateness_time)
        if lateness_hours <= threshold_hours:
            threshold_min = round(threshold_hours * 60)
            return (False, f'Retraso ({self.lateness_time}) no supera umbral ({threshold_min} min)')
        
        OvertimeModel = self.env['hr.attendance.overtime'].sudo()        
        # Crear registro de overtime con attendance_id y reason (agregados por este módulo)
        try:
            overtime_vals = {
                'employee_id': employee.id,
                'attendance_id': attendance_id,
                'date': self.check_date.date() if self.check_date else False,
                'duration': lateness_hours,
            }
            if 'attendance_id' in OvertimeModel._fields:
                overtime_vals['attendance_id'] = attendance_id
            if 'reason' in OvertimeModel._fields:
                overtime_vals['reason'] = f'Retraso en entrada: {self.lateness_time}'
            
            overtime = OvertimeModel.create(overtime_vals)
            return (overtime, f'Overtime creado | ID: {overtime.id} | Retraso: {lateness_hours:.2f} horas')
        
        except Exception as e:
            _logger.error(f"Error al crear overtime: {str(e)}")
            return (False, f'Error al crear overtime | Error: {str(e)}')
    
    def _map_to_work_entry(self, attendance_id):
        # Crea hr.work.entry basado en los datos de asistencia.
        self.ensure_one()
        employee = self._get_employee_from_registration()
        if not employee:
            return (False, 'Empleado no encontrado')
        
        WorkEntryModel = self.env['hr.work.entry'].sudo()
        attendance = self.env['hr.attendance'].sudo().browse(attendance_id)
        if not attendance.exists():
            return (False, f'Attendance ID {attendance_id} no encontrado')
        
        # Determinar tipo de entrada
        if self.check_type == 'entrada' and not attendance.check_out:
            # Entrada sin salida - No crear work entry hasta que se complete
            return (False, 'Entrada sin salida - Work entry se creará al registrar salida')
        
        if self.check_type == 'salida' and attendance.check_in and attendance.check_out:
            try:
                # Buscar tipo de work entry (WORK100 = Asistencia normal)
                work_entry_type = self.env.ref('hr_work_entry.work_entry_type_attendance', raise_if_not_found=False)
                
                if not work_entry_type:
                    work_entry_type = self.env['hr.work.entry.type'].sudo().search([('code', '=', 'WORK100')], limit=1)
                
                work_entry = WorkEntryModel.create({
                    'employee_id': employee.id,
                    'name': f'Asistencia {attendance.check_in.date()}',
                    'date_start': attendance.check_in,
                    'date_stop': attendance.check_out,
                    'work_entry_type_id': work_entry_type.id if work_entry_type else False,
                    'state': 'draft',
                })
                
                return (work_entry, f'Work Entry creado | ID: {work_entry.id} | Tipo: Jornada Normal')
            
            except Exception as e:
                _logger.error(f"Error al crear work entry: {str(e)}")
                return (False, f'Error al crear work entry | Error: {str(e)}')
        
        return (False, 'Condiciones no cumplidas para crear work entry')
    
    @api.model
    def process_pending_logs(self):
        # Procesa registros pendientes de importación a Odoo.
        _logger.info("="*80)
        _logger.info("INICIANDO PROCESAMIENTO DE ASISTENCIAS PENDIENTES - TAREA 0051")
        _logger.info("="*80)
        
        start_time = datetime.now()
        
        # 1. EXTRACCIÓN: Obtener registros pendientes
        pending_records = self.search([('log_status', '=', 'pendiente')], order='check_date asc, id asc')
        
        total_records = len(pending_records)
        _logger.info(f"Total de registros pendientes encontrados: {total_records}")
        
        if total_records == 0:
            _logger.info("No hay registros pendientes para procesar")
            return {'total_procesados': 0, 'exitosos': 0, 'errores': 0, 'detalles_errores': [], 'tiempo_ejecucion': '0 segundos'}
        
        exitosos = 0
        errores = 0
        detalles_errores = []
        
        for record in pending_records:
            try:
                _logger.info(f"\n--- Procesando registro ID: {record.id} | Employee: {record.registration_number} | Tipo: {record.check_type} | Fecha: {record.check_date}")
                
                # 2.1 VALIDACIÓN
                is_valid, validation_message = record._validate_for_import()
                if not is_valid:
                    # Marcar como error
                    record.write({'log_status': 'error', 'log_message': validation_message})
                    errores += 1
                    detalles_errores.append({'id': record.id, 'employee': record.registration_number, 'error': validation_message})
                    _logger.warning(f"Validación fallida: {validation_message}")
                    continue
                
                # 2.2 MAPEO A hr.attendance
                attendance, attendance_message = record._map_to_attendance()
                if not attendance:
                    # Error al crear/actualizar attendance
                    record.write({'log_status': 'error', 'log_message': attendance_message })
                    errores += 1
                    detalles_errores.append({'id': record.id, 'employee': record.registration_number, 'error': attendance_message})
                    _logger.warning(f"Error en attendance: {attendance_message}")
                    continue
                
                # Registro exitoso hasta ahora
                messages = [attendance_message]
                # 2.3 MAPEO A hr.attendance.overtime (si aplica)
                if record.check_type == 'entrada' and record.lateness_time:
                    overtime, overtime_message = record._map_to_overtime(attendance.id)
                    if overtime:
                        messages.append(overtime_message)
                        _logger.info(f"Overtime creado: {overtime_message}")
                    else:
                        # No es error, solo información
                        _logger.info(f"Overtime no creado: {overtime_message}")
                
                # 2.4 MAPEO A hr.work.entry (si aplica)
                if record.check_type == 'salida':
                    work_entry, work_entry_message = record._map_to_work_entry(attendance.id)
                    if work_entry:
                        messages.append(work_entry_message)
                        _logger.info(f"Work Entry creado: {work_entry_message}")
                    else:
                        # No es error, solo información
                        _logger.info(f"Work Entry: {work_entry_message}")
                
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
        
        _logger.info("\n" + "="*80)
        _logger.info("RESUMEN DE PROCESAMIENTO:")
        _logger.info(f"Total procesados: {total_records}")
        _logger.info(f"Exitosos: {exitosos}")
        _logger.info(f"Errores: {errores}")
        _logger.info(f"Tasa de éxito: {(exitosos/total_records*100) if total_records > 0 else 0:.2f}%")
        _logger.info(f"Tiempo de ejecución: {execution_time:.2f} segundos")
        _logger.info("="*80 + "\n")
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
