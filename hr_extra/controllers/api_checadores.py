# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime, timedelta
from functools import wraps
from odoo import http, SUPERUSER_ID
from odoo.http import request, Response
from odoo.exceptions import AccessDenied

# Verificar disponibilidad de PyJWT al cargar el módulo
try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

_logger = logging.getLogger(__name__)


class ApiChecadoresController(http.Controller):
    # Controlador principal para la API de Checadores con JWT.

    def _check_jwt_available(self):
        # Verifica si PyJWT está disponible
        if not JWT_AVAILABLE:
            return False, self._error_response('PyJWT no está instalado. Instale con: pip install PyJWT', status=500, error_code='JWT_NOT_INSTALLED')
        return True, None

    def _get_jwt_secret(self):
        # Obtiene la clave secreta para firmar JWT
        secret = request.env['ir.config_parameter'].sudo().get_param('api_checadores.jwt_secret', '')
        if not secret:
            # Generar una nueva si no existe
            import secrets
            secret = secrets.token_urlsafe(32)
            request.env['ir.config_parameter'].sudo().set_param('api_checadores.jwt_secret', secret)
        return secret

    def _json_response(self, data, status=200):
        # Genera respuesta JSON estándar.
        return Response(
            json.dumps(data, ensure_ascii=False, default=str),
            status=status,
            mimetype='application/json',
            headers=[('Access-Control-Allow-Origin', '*'), ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'), 
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization'),])

    def _error_response(self, message, status=400, error_code=None):
        # Genera respuesta de error estándar.
        return self._json_response({
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'error': {'code': error_code or f'ERR_{status}', 'message': message,}}, status=status)

    def _validate_jwt_token(self):
        """ Valida el token JWT enviado en el header Authorization.
        Returns:
            tuple: (is_valid, error_response or user_data) """
        # Verificar que PyJWT esté disponible
        jwt_ok, error = self._check_jwt_available()
        if not jwt_ok:
            return False, error
        
        api_enabled = request.env['ir.config_parameter'].sudo().get_param('api_checadores.enabled', 'False')
        if api_enabled.lower() != 'true':
            return False, self._error_response('API de checadores no está habilitada', status=503, error_code='API_DISABLED')
        
        # Obtener token del header Authorization
        auth_header = request.httprequest.headers.get('Authorization', '')
        
        if not auth_header:
            return False, self._error_response('Token de autorización no proporcionado. Incluya el header Authorization: Bearer <token>', status=401,
                error_code='MISSING_TOKEN')
        
        # Verificar formato "Bearer <token>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return False, self._error_response('Formato de Authorization inválido. Use: Bearer <token>', status=401, error_code='INVALID_AUTH_FORMAT')
        
        token = parts[1]
        secret = self._get_jwt_secret()
        
        try:
            # Decodificar y validar token
            payload = jwt.decode(token, secret, algorithms=['HS256'])
            
            # Verificar expiración
            if datetime.fromtimestamp(payload['exp']) < datetime.now():
                return False, self._error_response('Token expirado', status=401, error_code='TOKEN_EXPIRED')
            
            # Token válido
            return True, payload            
        except jwt.ExpiredSignatureError:
            _logger.warning(f"API Checadores: Token expirado desde IP: {request.httprequest.remote_addr}")
            return False, self._error_response('Token expirado', status=401, error_code='TOKEN_EXPIRED')
        except jwt.InvalidTokenError as e:
            _logger.warning(f"API Checadores: Token inválido desde IP: {request.httprequest.remote_addr} - {str(e)}")
            return False, self._error_response('Token inválido', status=401, error_code='INVALID_TOKEN')
        except Exception as e:
            _logger.error(f"API Checadores: Error validando token: {str(e)}")
            return False, self._error_response('Error validando token', status=500, error_code='TOKEN_VALIDATION_ERROR')

    # === ENDPOINTS ===
    @http.route('/api/v1/auth/login', type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False)
    def login(self, **kwargs):
        """Autenticación para obtener token JWT.
        
        Body JSON:
            {"username": "api_user", "password": "api_password"}
        
        Returns:
            {"status": "success", "token": "eyJ...", "expires_in": 86400, "token_type": "Bearer"}
        """
        if request.httprequest.method == 'OPTIONS':
            return self._json_response({'status': 'ok'})
        
        try:
            # Verificar que PyJWT esté disponible
            if not JWT_AVAILABLE:
                return self._error_response('PyJWT no está instalado', status=500, error_code='JWT_NOT_INSTALLED')
            
            # Verificar que la API esté habilitada
            api_enabled = request.env['ir.config_parameter'].sudo().get_param('api_checadores.enabled', 'False')
            if api_enabled.lower() != 'true':
                return self._error_response('API de checadores no está habilitada', status=503, error_code='API_DISABLED')
            
            # Parsear body JSON
            try:
                data = json.loads(request.httprequest.data.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return self._error_response('Body JSON inválido', status=400, error_code='INVALID_JSON')
            
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                return self._error_response('Username y password son requeridos', status=400, error_code='MISSING_CREDENTIALS')
            
            # Obtener credenciales configuradas
            ICP = request.env['ir.config_parameter'].sudo()
            config_username = ICP.get_param('api_checadores.username', '')
            config_password = ICP.get_param('api_checadores.password', '')
            
            if not config_username or not config_password:
                return self._error_response('Credenciales no configuradas en el servidor', status=500, error_code='CREDENTIALS_NOT_CONFIGURED')
            
            # Validar credenciales
            if username != config_username or password != config_password:
                _logger.warning(f"API Checadores: Login fallido para '{username}' desde IP: {request.httprequest.remote_addr}")
                return self._error_response('Credenciales inválidas', status=401, error_code='INVALID_CREDENTIALS')
            
            # Generar token JWT
            secret = self._get_jwt_secret()
            expires_in = 86400  # 24 horas
            
            payload = {
                'username': username,
                'iat': datetime.now().timestamp(),
                'exp': (datetime.now() + timedelta(seconds=expires_in)).timestamp()}
            
            token = jwt.encode(payload, secret, algorithm='HS256')
            
            _logger.info(f"API Checadores: Login exitoso para '{username}' desde IP: {request.httprequest.remote_addr}")
            
            return self._json_response({
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'token': token,
                'expires_in': expires_in,
                'token_type': 'Bearer'})
            
        except Exception as e:
            _logger.error(f"API Checadores Login Error: {str(e)}", exc_info=True)
            return self._error_response(f'Error interno: {str(e)}', status=500, error_code='INTERNAL_ERROR')


    @http.route('/api/v1/health', type='http', auth='none', methods=['GET'], csrf=False)
    def health_check(self):
        # Health check del servicio (sin autenticación).
        api_enabled = request.env['ir.config_parameter'].sudo().get_param('api_checadores.enabled', 'False')
        return self._json_response({
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'service': 'api_checadores',
            'version': '2.5.1',
            'authentication': 'JWT',
            'jwt_available': JWT_AVAILABLE,
            'api_enabled': api_enabled.lower() == 'true', })

    @http.route('/api/v1/employees', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def get_employees(self, **kwargs):
        """ Obtiene lista de empleados activos.
        
        Headers:
            Authorization: Bearer <token>
        
        Query Parameters:
            - search: Búsqueda por nombre o número de empleado
            - department_id: Filtrar por ID de departamento
            - registration_number: Buscar empleado específico por número
            - with_contract: Solo empleados con contrato vigente (true/false)
            - active_only: Solo empleados activos (default true)
            - limit: Límite de resultados (default 100, max 1000)
            - offset: Desplazamiento para paginación (default 0)
        """
        if request.httprequest.method == 'OPTIONS':
            return self._json_response({'status': 'ok'})
        
        is_valid, result = self._validate_jwt_token()
        if not is_valid:
            return result
        
        try:
            filters = {'active_only': kwargs.get('active_only', 'true').lower() == 'true', 
                'with_contract': kwargs.get('with_contract', 'false').lower() == 'true',}
            if kwargs.get('department_id'):
                filters['department_id'] = kwargs['department_id']
            if kwargs.get('registration_number'):
                filters['registration_number'] = kwargs['registration_number']
            if kwargs.get('search'):
                filters['search'] = kwargs['search']
            if kwargs.get('limit'):
                filters['limit'] = kwargs['limit']
            if kwargs.get('offset'):
                filters['offset'] = kwargs['offset']
            
            # Usar sudo() con el usuario SUPERUSER_ID para evitar problemas de contexto
            HrEmployee = request.env(user=SUPERUSER_ID)['hr.employee']
            result_data = HrEmployee.get_employees_for_api(filters)
            
            _logger.info(f"API Checadores: Consulta empleados exitosa desde IP {request.httprequest.remote_addr}. "
                f"Usuario JWT: {result.get('username')}. Total: {result_data['total_count']}, Retornados: {result_data['returned_count']}")
            
            return self._json_response({
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'count': result_data['returned_count'],
                'total': result_data['total_count'],
                'limit': result_data['limit'],
                'offset': result_data['offset'],
                'filters_applied': filters,
                'data': result_data['employees'],
            })
        except Exception as e:
            _logger.error(f"API Checadores Error: {str(e)}", exc_info=True)
            return self._error_response(f'Error interno del servidor: {str(e)}', status=500, error_code='INTERNAL_ERROR')


    @http.route('/api/v1/employees/<int:employee_id>', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def get_employee_by_id(self, employee_id, **kwargs):
        """[DEPRECATED] Obtiene datos de un empleado específico por ID.
        
        NOTA: Este endpoint está deprecado. Use /api/v1/employees/by-number/<registration_number> en su lugar.
        
        Se mantiene por compatibilidad hacia atrás. """
        if request.httprequest.method == 'OPTIONS':
            return self._json_response({'status': 'ok'})
        
        is_valid, result = self._validate_jwt_token()
        if not is_valid:
            return result
        
        try:
            employee = request.env(user=SUPERUSER_ID)['hr.employee'].browse(employee_id)
            
            if not employee.exists():
                return self._error_response(f'Empleado con ID {employee_id} no encontrado', status=404, error_code='EMPLOYEE_NOT_FOUND')
            
            employee_data = employee.get_employee_data_for_api()
            _logger.info(f"API Checadores: Consulta empleado {employee_id} desde {request.httprequest.remote_addr}. "
                f"Usuario JWT: {result.get('username')}" )
            
            return self._json_response({
                'status': 'success', 
                'timestamp': datetime.now().isoformat(), 
                'deprecated': True,
                'message': 'Este endpoint está deprecado. Use /api/v1/employees/by-number/<registration_number>',
                'data': employee_data,
            })
        except Exception as e:
            _logger.error(f"API Checadores Error (employee/{employee_id}): {str(e)}", exc_info=True)
            return self._error_response(f'Error interno del servidor: {str(e)}', status=500, error_code='INTERNAL_ERROR')


    @http.route('/api/v1/employees/by-number/<string:registration_number>', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def get_employee_by_registration_number(self, registration_number, **kwargs):
        """Obtiene datos de un empleado específico por número de empleado (registration_number).
        
        Este es el endpoint recomendado para buscar empleados individuales.
        
        Headers:
            Authorization: Bearer <token>
        
        Path Parameters:
            registration_number: Número de empleado (ej: "00271")
        
        Returns: {
            "status": "success",
            "data": {
                "id": 425,
                "registration_number": "00271",
                "full_name": "ABEL CRUZ RIVERA",
                ...
            }
        }
        """
        if request.httprequest.method == 'OPTIONS':
            return self._json_response({'status': 'ok'})
        
        is_valid, result = self._validate_jwt_token()
        if not is_valid:
            return result
        
        try:
            employee = request.env(user=SUPERUSER_ID)['hr.employee'].search([
                ('registration_number', '=', registration_number)
            ], limit=1)
            
            if not employee:
                return self._error_response(
                    f'Empleado con número {registration_number} no encontrado', 
                    status=404, 
                    error_code='EMPLOYEE_NOT_FOUND'
                )
            
            employee_data = employee.get_employee_data_for_api()
            _logger.info(f"API Checadores: Consulta empleado por número {registration_number} "
                f"desde {request.httprequest.remote_addr}. Usuario JWT: {result.get('username')}")
            
            return self._json_response({
                'status': 'success', 
                'timestamp': datetime.now().isoformat(), 
                'data': employee_data,
            })
        except Exception as e:
            _logger.error(f"API Checadores Error (employee/by-number/{registration_number}): {str(e)}", exc_info=True)
            return self._error_response(f'Error interno del servidor: {str(e)}', status=500, error_code='INTERNAL_ERROR')


    @http.route('/api/v1/departments', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def get_departments(self, **kwargs):
        # Obtiene lista de departamentos disponibles.
        if request.httprequest.method == 'OPTIONS':
            return self._json_response({'status': 'ok'})
        
        is_valid, result = self._validate_jwt_token()
        if not is_valid:
            return result
        
        try:
            departments = request.env(user=SUPERUSER_ID)['hr.department'].search([])
            departments_data = [{'id': dept.id, 'name': dept.name, 'manager': dept.manager_id.name if dept.manager_id else '', 
                'parent_department': dept.parent_id.name if dept.parent_id else '', 'employee_count': dept.total_employee,} for dept in departments]
            return self._json_response({'status': 'success', 'timestamp': datetime.now().isoformat(), 'count': len(departments_data), 'data': departments_data,})
        except Exception as e:
            _logger.error(f"API Checadores Error (departments): {str(e)}", exc_info=True)
            return self._error_response(f'Error interno del servidor: {str(e)}', status=500, error_code='INTERNAL_ERROR')


    @http.route('/api/v1/job_positions', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def get_job_positions(self, **kwargs):
        """Obtiene lista de puestos de trabajo (job positions) disponibles.
        
        Headers:
            Authorization: Bearer <token>
        
        Returns:
            {
                "status": "success",
                "count": 50,
                "data": [
                    {
                        "id": 1,
                        "name": "Gerente de Proyectos",
                        "department": "Operaciones",
                        "department_id": 5,
                        "employee_count": 12,
                        "description": "Descripción del puesto"
                    }
                ]
            }
        """
        if request.httprequest.method == 'OPTIONS':
            return self._json_response({'status': 'ok'})
        
        is_valid, result = self._validate_jwt_token()
        if not is_valid:
            return result
        
        try:
            jobs = request.env(user=SUPERUSER_ID)['hr.job'].search([])
            
            jobs_data = []
            for job in jobs:
                # Contar empleados activos con este puesto
                employee_count = request.env(user=SUPERUSER_ID)['hr.employee'].search_count([
                    ('job_id', '=', job.id),
                    ('active', '=', True)
                ])
                
                jobs_data.append({
                    'id': job.id,
                    'name': job.name or '',
                    'department': job.department_id.name if job.department_id else '',
                    'department_id': job.department_id.id if job.department_id else None,
                    'employee_count': employee_count,
                    'description': job.description or '',
                })
            
            _logger.info(f"API Checadores: Consulta job_positions exitosa desde IP {request.httprequest.remote_addr}. "
                f"Usuario JWT: {result.get('username')}. Puestos: {len(jobs_data)}")
            
            return self._json_response({
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'count': len(jobs_data),
                'data': jobs_data,
            })
        except Exception as e:
            _logger.error(f"API Checadores Error (job_positions): {str(e)}", exc_info=True)
            return self._error_response(f'Error interno del servidor: {str(e)}', status=500, error_code='INTERNAL_ERROR')


    @http.route('/api/v1/schedules', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def get_schedules(self, **kwargs):
        # Obtiene lista de horarios de trabajo disponibles.
        if request.httprequest.method == 'OPTIONS':
            return self._json_response({'status': 'ok'})
        
        is_valid, result = self._validate_jwt_token()
        if not is_valid:
            return result
        
        try:
            calendars = request.env(user=SUPERUSER_ID)['resource.calendar'].search([])
            day_mapping = {'0': 'Lunes', '1': 'Martes', '2': 'Miércoles', '3': 'Jueves', '4': 'Viernes', '5': 'Sábado', '6': 'Domingo',}
            
            schedules_data = []
            for cal in calendars:
                attendance_data = []
                for att in cal.attendance_ids:
                    hours = int(att.hour_from)
                    minutes = int((att.hour_from - hours) * 60)
                    hour_from = f"{hours:02d}:{minutes:02d}:00"                    
                    hours = int(att.hour_to)
                    minutes = int((att.hour_to - hours) * 60)
                    hour_to = f"{hours:02d}:{minutes:02d}:00"
                    
                    attendance_data.append({'day_of_week': day_mapping.get(att.dayofweek, att.dayofweek), 'day_of_week_number': int(att.dayofweek),
                        'hour_from': hour_from, 'hour_to': hour_to, 'name': att.name or '',})
                
                schedules_data.append({'id': cal.id, 'name': cal.name, 'tolerance_minutes': cal.tolerance_minutes or 15, 'hours_per_week': cal.hours_per_week,
                    'attendance': attendance_data, })
            return self._json_response({'status': 'success', 'timestamp': datetime.now().isoformat(), 'count': len(schedules_data), 'data': schedules_data,})
        except Exception as e:
            _logger.error(f"API Checadores Error (schedules): {str(e)}", exc_info=True)
            return self._error_response(f'Error interno del servidor: {str(e)}', status=500, error_code='INTERNAL_ERROR')


    @http.route('/api/v1/attendances', type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def attendance_create(self, **kw):
        """Crea un registro de asistencia en ctrol.asistencias.
        
        Body JSON: {
            "registration_number": "00271",
            "check_type": "entrada",
            "check_date": "2026-01-30T08:00:00",
            "photo_url": "http://...",
            "latitude": 20.67,
            "longitude": -103.33,
            "log_status": "pendiente",
            "lateness_time": "00:15",
            "left_early_time": "00:00",
            "is_active": 1,
            "verification_status": "auto",
            "match_percentage": 98,
            "log_message": "Registro exitoso"
        }
        
        Validaciones (v2.5.0):
        - Formato de fecha erróneo: HTTP 400, code=INVALID_DATE_FORMAT
        - Fecha fuera de ±1 día: HTTP 400, code=INVALID_DATE_RANGE
        - Más de 6 checks por día: HTTP 400, code=MAX_CHECKS_EXCEEDED
        - Fecha válida: Guarda con status="success"
        
        Returns: {
            "status": "success",
            "data": {...},
            "checks_today": 3
        }
        """
        if request.httprequest.method == 'OPTIONS':
            return self._json_response({'status': 'ok'})
        
        # Validar JWT
        is_valid, result = self._validate_jwt_token()
        if not is_valid:
            return result
        
        try:
            # Parsear datos del body
            data = json.loads(request.httprequest.data.decode('utf-8'))
          
            # Validar campos requeridos
            if not data.get('registration_number'):
                return self._error_response('Campo requerido: registration_number', status=400, error_code='MISSING_REGISTRATION_NUMBER')
            
            if not data.get('check_type'):
                return self._error_response('Campo requerido: check_type', status=400, error_code='MISSING_CHECK_TYPE')
            if not data.get('check_date'):
                return self._error_response('Campo requerido: check_date', status=400, error_code='MISSING_CHECK_DATE')
            if data.get('check_type') not in ['entrada', 'salida']:
                return self._error_response('check_type debe ser "entrada" o "salida"', status=400, error_code='INVALID_CHECK_TYPE')
            
            # Validar formato de fecha - Si es inválido, NO guardar y devolver error
            try:
                check_datetime = datetime.fromisoformat(data['check_date'].replace('Z', '+00:00'))
            except (ValueError, TypeError) as e:
                return self._error_response(
                    f'Formato de fecha inválido: {data["check_date"]}. Use formato ISO 8601 (YYYY-MM-DDTHH:MM:SS)',
                    status=400,
                    error_code='INVALID_DATE_FORMAT'
                )
            
            # Usar SUPERUSER_ID para crear registro
            env = request.env(user=SUPERUSER_ID)
            
            # Validar que empleado existe por registration_number
            employee = env['hr.employee'].search([('registration_number', '=', data['registration_number'])], limit=1)
            if not employee:
                return self._error_response(
                    f'Empleado con número {data["registration_number"]} no encontrado',
                    status=404,
                    error_code='EMPLOYEE_NOT_FOUND'
                )
            
            now = datetime.now()
            
            # VALIDACIÓN 1: Fecha dentro de ±1 día (según TXT)
            one_day_ago = now - timedelta(days=1)
            one_day_ahead = now + timedelta(days=1)
            
            if check_datetime < one_day_ago or check_datetime > one_day_ahead:
                return self._error_response(
                    f'La fecha de registro debe estar dentro de ±1 día de la fecha actual. '
                    f'Fecha enviada: {check_datetime.strftime("%Y-%m-%d %H:%M:%S")}, '
                    f'Rango permitido: {one_day_ago.strftime("%Y-%m-%d %H:%M:%S")} a {one_day_ahead.strftime("%Y-%m-%d %H:%M:%S")}',
                    status=400,
                    error_code='INVALID_DATE_RANGE'
                )
            
            # VALIDACIÓN 2: Máximo 6 checks por empleado por día (según TXT)
            check_date_only = check_datetime.date()
            checks_today = env['ctrol.asistencias'].search_count([
                ('registration_number', '=', data['registration_number']),
                ('check_date', '>=', f'{check_date_only} 00:00:00'),
                ('check_date', '<=', f'{check_date_only} 23:59:59')
            ])
            
            if checks_today >= 6:
                return self._error_response(
                    f'El empleado {data["registration_number"]} ya tiene {checks_today} registros para el día {check_date_only}. Máximo permitido: 6',
                    status=400,
                    error_code='MAX_CHECKS_EXCEEDED'
                )
            
            # Preparar datos para crear registro
            data['status'] = 'success'
            data['observaciones'] = ''
            
            # Crear registro en ctrol.asistencias
            CtrolAsistencias = env['ctrol.asistencias']
            attendance = CtrolAsistencias.create_from_checador(data)
            
            # Actualizar contador de checks (después de crear)
            checks_today_final = checks_today + 1
            
            _logger.info(f"API Checadores: Asistencia creada - ID: {attendance.id}, "
                        f"Empleado: {data['registration_number']}, "
                        f"Checks hoy: {checks_today_final}, Usuario JWT: {result.get('username')}")
            
            return self._json_response({
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': attendance.to_json(),
                'checks_today': checks_today_final
            })
            
        except json.JSONDecodeError:
            return self._error_response('Body JSON inválido', status=400, error_code='INVALID_JSON')
        except Exception as e:
            _logger.error(f"API Checadores Error (attendance_create): {str(e)}", exc_info=True)
            return self._error_response(f'Error interno del servidor: {str(e)}', status=500, error_code='INTERNAL_ERROR')


    @http.route('/api/v1/attendances', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def attendance_list(self, **kw):
        """Obtiene lista de asistencias desde ctrol.asistencias con paginación.
        
        Query Parameters (en body JSON para GET):
            - registration_number: Filtrar por número de empleado
            - check_type: Filtrar por tipo (entrada/salida)
            - date_from: Fecha desde (YYYY-MM-DD)
            - date_to: Fecha hasta (YYYY-MM-DD)
            - log_status: Filtrar por estado (pendiente/error/importada)
            - status: Filtrar por status de validación (success/error)
            - limit: Número máximo de registros (default 100, max 1000)
            - offset: Desplazamiento para paginación (default 0)
        
        Returns: {
            "status": "success",
            "count": 10,          <- Registros en esta página
            "total": 150,         <- Total que coinciden con filtros
            "limit": 100,
            "offset": 0,
            "data": [...]
        } """
        # Validar JWT
        is_valid, result = self._validate_jwt_token()
        if not is_valid:
            return result
        
        try:
            # Parsear filtros del body (si existen)
            filters = {}
            if request.httprequest.data:
                try:
                    filters = json.loads(request.httprequest.data.decode('utf-8'))
                except:
                    pass
            
            # Construir dominio de búsqueda
            domain = []
            # Filtrar por registration_number (v2.4.0)
            if filters.get('registration_number'):
                domain.append(('registration_number', '=', filters['registration_number']))
            
            # Mantener compatibilidad con employee_id (deprecated)
            if filters.get('employee_id'):
                domain.append(('employee_id', '=', int(filters['employee_id'])))
            if filters.get('check_type'):
                domain.append(('check_type', '=', filters['check_type']))
            if filters.get('log_status'):
                domain.append(('log_status', '=', filters['log_status']))
            
            # Filtro por status de validación (T0049)
            if filters.get('status'):
                domain.append(('status', '=', filters['status']))
            
            if filters.get('date_from'):
                domain.append(('check_date', '>=', filters['date_from']))
            if filters.get('date_to'):
                domain.append(('check_date', '<=', filters['date_to']))
            
            # Paginación - limit
            limit = int(filters.get('limit', 100))
            if limit > 1000:
                limit = 1000  # Máximo 1000 registros por query
            if limit < 1:
                limit = 100  # Mínimo 1, default 100
            
            # Paginación - offset (T0049)
            offset = int(filters.get('offset', 0))
            if offset < 0:
                offset = 0  # No permitir offset negativo
            
            # Usar SUPERUSER_ID para consultar
            env = request.env(user=SUPERUSER_ID)
            
            # Modelo de asistencias
            CtrolAsistencias = env['ctrol.asistencias']
            
            # Obtener total de registros que coinciden (para paginación)
            total_count = CtrolAsistencias.search_count(domain)
            
            # Buscar registros con paginación
            attendances = CtrolAsistencias.search(domain, limit=limit, offset=offset, order='check_date desc, id desc')
            
            # Convertir a JSON
            attendances_data = [att.to_json() for att in attendances]
            
            _logger.info(f"API Checadores: Consulta asistencias - "
                        f"Registros: {len(attendances_data)}/{total_count}, "
                        f"Limit: {limit}, Offset: {offset}, "
                        f"Usuario JWT: {result.get('username')}")
            
            return self._json_response({'status': 'success', 'timestamp': datetime.now().isoformat(), 'count': len(attendances_data), 'total': total_count,
                'limit': limit, 'offset': offset, 'filters_applied': filters, 'data': attendances_data})
        except Exception as e:
            _logger.error(f"API Checadores Error (attendance_list): {str(e)}", exc_info=True)
            return self._error_response(f'Error interno del servidor: {str(e)}', status=500, error_code='INTERNAL_ERROR')

    
    @http.route('/api/v1/employees/sync', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def employees_sync(self, **kw):
        """Sincronización incremental de empleados.
        
        Devuelve solo empleados modificados desde la última sincronización exitosa.
        Registra cada sincronización en checador.sync.log para tracking.
        
        Query Parameters:
            - device_id: Identificador del dispositivo (opcional, para tracking por dispositivo)
            - limit: Límite de resultados (default 1000)
            - offset: Desplazamiento para paginación
        
        Headers:
            Authorization: Bearer <token>
        
        Lógica:
            1. Busca última sincronización exitosa en checador.sync.log
            2. Si no existe (primera vez), devuelve TODOS los empleados
            3. Si existe, devuelve empleados con write_date > última_sync
            4. Registra la sincronización actual en el log
        
        Returns:
            {
                "status": "success",
                "sync_id": 45,
                "last_sync": "2026-02-05T18:00:00",
                "current_sync": "2026-02-06T10:00:00",
                "is_first_sync": false,
                "count": 3,
                "total": 3,
                "data": [...]} """
        if request.httprequest.method == 'OPTIONS':
            return self._json_response({'status': 'ok'})
        
        # Validar JWT
        is_valid, result = self._validate_jwt_token()
        if not is_valid:
            return result
        
        try:
            # Obtener parámetros
            device_id = kw.get('device_id', '')
            limit = min(int(kw.get('limit', 1000)), 1000)
            offset = int(kw.get('offset', 0))
            
            if limit < 1:
                limit = 1000
            if offset < 0:
                offset = 0
            
            # Usar SUPERUSER_ID
            env = request.env(user=SUPERUSER_ID)
            SyncLog = env['checador.sync.log']
            Employee = env['hr.employee']
            
            # Obtener última sincronización exitosa
            last_sync_date = SyncLog.get_last_successful_sync(sync_type='employees', device_id=device_id if device_id else None)
            current_sync_date = datetime.now()
            is_first_sync = last_sync_date is None
            
            # Construir dominio de búsqueda
            if is_first_sync:
                # Primera sincronización: todos los empleados activos
                domain = [('active', '=', True)]
                _logger.info(f"API Sync: Primera sincronización para device_id={device_id or 'global'}")
            else:
                # Sincronización incremental: solo modificados desde última sync
                # Incluye activos e inactivos (para detectar bajas)
                domain = [('write_date', '>', last_sync_date)]
                _logger.info(f"API Sync: Sincronización incremental desde {last_sync_date} para device_id={device_id or 'global'}")
            
            total_count = Employee.search_count(domain)
            employees = Employee.search(domain, limit=limit, offset=offset, order='write_date desc')
            
            # Convertir a JSON con campo write_date adicional
            employees_data = []
            for emp in employees:
                emp_data = emp.get_employee_data_for_api()
                emp_data['write_date'] = emp.write_date.isoformat() if emp.write_date else ''
                emp_data['create_date'] = emp.create_date.isoformat() if emp.create_date else ''
                employees_data.append(emp_data)
            
            # Registrar sincronización exitosa
            sync_record = SyncLog.register_sync(sync_type='employees', device_id=device_id, records_count=len(employees_data), status='success',
                ip_address=request.httprequest.remote_addr, user_jwt=result.get('username', ''), last_sync_ref=last_sync_date,
                notes=f"Sincronización {'inicial' if is_first_sync else 'incremental'}. Total modificados: {total_count}")
            
            _logger.info(f"API Sync: Sincronización exitosa - "
                        f"sync_id={sync_record.id}, "
                        f"device_id={device_id or 'global'}, "
                        f"registros={len(employees_data)}/{total_count}, "
                        f"primera_sync={is_first_sync}")
            
            return self._json_response({'status': 'success', 'timestamp': current_sync_date.isoformat(), 'sync_id': sync_record.id, 
                'last_sync': last_sync_date.isoformat() if last_sync_date else None, 'current_sync': current_sync_date.isoformat(),
                'is_first_sync': is_first_sync, 'count': len(employees_data), 'total': total_count, 'limit': limit, 'offset': offset,
                'device_id': device_id or None, 'data': employees_data})
            
        except Exception as e:
            _logger.error(f"API Checadores Error (employees_sync): {str(e)}", exc_info=True)
            # Intentar registrar error en log
            try:
                env = request.env(user=SUPERUSER_ID)
                env['checador.sync.log'].register_sync(sync_type='employees', device_id=kw.get('device_id', ''), records_count=0, status='error',
                    ip_address=request.httprequest.remote_addr, user_jwt=result.get('username', '') if isinstance(result, dict) else '',
                    notes=f"Error: {str(e)}")
            except:
                pass  # Si falla el log de error, no interrumpir
            
            return self._error_response(f'Error interno del servidor: {str(e)}', status=500, error_code='INTERNAL_ERROR')
