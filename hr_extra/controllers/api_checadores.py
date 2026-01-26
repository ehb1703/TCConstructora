# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime, timedelta
from functools import wraps

from odoo import http, _
from odoo.http import request, Response
from odoo.exceptions import AccessDenied

# Intentar importar PyJWT
try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    _logger_import = logging.getLogger(__name__)
    _logger_import.error("PyJWT no está instalado. La API de checadores no funcionará. Instala con: pip install PyJWT")

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
        
        Body JSON: {
                "username": "api_user",
                "password": "api_password"
            }
        
        Returns: {
                "status": "success",
                "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "expires_in": 86400,
                "token_type": "Bearer"
            } """
        if request.httprequest.method == 'OPTIONS':
            return self._json_response({'status': 'ok'})
        
        try:
            # Verificar que PyJWT esté disponible
            if not JWT_AVAILABLE:
                return self._json_response({
                    'status': 'error',
                    'error': {'code': 'JWT_NOT_INSTALLED', 'message': 'PyJWT no está instalado. Instale con: pip install PyJWT'}
                }, status=500)
            
            # Verificar que la API esté habilitada
            api_enabled = request.env['ir.config_parameter'].sudo().get_param('api_checadores.enabled', 'False')
            if api_enabled.lower() != 'true':
                return self._json_response({
                    'status': 'error',
                    'error': {'code': 'API_DISABLED', 'message': 'API de checadores no está habilitada'}}, status=503)
            
            # Obtener credenciales del body
            try:
                data = json.loads(request.httprequest.data.decode('utf-8'))
            except:
                return self._json_response({
                    'status': 'error',
                    'error': {'code': 'INVALID_JSON', 'message': 'Body JSON inválido'}}, status=400)
            
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                return self._json_response({
                    'status': 'error',
                    'error': {'code': 'MISSING_CREDENTIALS', 'message': 'Username y password son requeridos'}}, status=400)
            
            # Obtener credenciales configuradas
            config_username = request.env['ir.config_parameter'].sudo().get_param('api_checadores.username', '')
            config_password = request.env['ir.config_parameter'].sudo().get_param('api_checadores.password', '')
            
            if not config_username or not config_password:
                return self._json_response({
                    'status': 'error',
                    'error': {'code': 'CREDENTIALS_NOT_CONFIGURED', 'message': 'Credenciales no configuradas en el servidor'}}, status=500)
            
            # Validar credenciales
            if username != config_username or password != config_password:
                _logger.warning(f"API Checadores: Intento de login fallido para usuario '{username}' "
                    f"desde IP: {request.httprequest.remote_addr}")
                return self._json_response({
                    'status': 'error',
                    'error': {'code': 'INVALID_CREDENTIALS', 'message': 'Credenciales inválidas'}}, status=401)
            
            # Generar token JWT
            secret = self._get_jwt_secret()
            expires_in = 86400  # 24 horas
            
            payload = {
                'username': username,
                'iat': datetime.now().timestamp(),
                'exp': (datetime.now() + timedelta(seconds=expires_in)).timestamp()}
            
            token = jwt.encode(payload, secret, algorithm='HS256')
            
            _logger.info(f"API Checadores: Login exitoso para usuario '{username}' "
                f"desde IP: {request.httprequest.remote_addr}")
            
            return self._json_response({
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'token': token,
                'expires_in': expires_in,
                'token_type': 'Bearer'})
            
        except Exception as e:
            _logger.error(f"API Checadores Login Error: {str(e)}", exc_info=True)
            return self._json_response({
                'status': 'error',
                'error': {'code': 'INTERNAL_ERROR', 'message': f'Error interno del servidor: {str(e)}'}}, status=500)


    @http.route('/api/v1/health', type='http', auth='none', methods=['GET'], csrf=False)
    def health_check(self):
        # Health check del servicio (sin autenticación).
        api_enabled = request.env['ir.config_parameter'].sudo().get_param('api_checadores.enabled', 'False')
        return self._json_response({
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'service': 'api_checadores',
            'version': '1.2',
            'authentication': 'JWT',
            'jwt_available': JWT_AVAILABLE,
            'api_enabled': api_enabled.lower() == 'true', })

    @http.route('/api/v1/employees', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def get_employees(self, **kwargs):
        """ Obtiene lista de empleados activos.
        
        Headers:
            Authorization: Bearer <token>
        
        Query Parameters:
            - department_id: Filtrar por ID de departamento
            - registration_number: Buscar empleado específico por número
            - with_contract: Solo empleados con contrato vigente (true/false)
            - active_only: Solo empleados activos (default true) """
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
            
            # Usar sudo() con el usuario SUPERUSER_ID para evitar problemas de contexto
            from odoo import SUPERUSER_ID
            HrEmployee = request.env(user=SUPERUSER_ID)['hr.employee']
            employees_data = HrEmployee.get_employees_for_api(filters)
            
            _logger.info(f"API Checadores: Consulta exitosa desde IP {request.httprequest.remote_addr}. "
                f"Usuario JWT: {result.get('username')}. Empleados: {len(employees_data)}")
            
            return self._json_response({
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'count': len(employees_data),
                'filters_applied': filters,
                'data': employees_data,})
        except Exception as e:
            _logger.error(f"API Checadores Error: {str(e)}", exc_info=True)
            return self._error_response(f'Error interno del servidor: {str(e)}', status=500, error_code='INTERNAL_ERROR')


    @http.route('/api/v1/employees/<int:employee_id>', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def get_employee_by_id(self, employee_id, **kwargs):
        # Obtiene datos de un empleado específico por ID.
        if request.httprequest.method == 'OPTIONS':
            return self._json_response({'status': 'ok'})
        
        is_valid, result = self._validate_jwt_token()
        if not is_valid:
            return result
        
        try:
            from odoo import SUPERUSER_ID
            employee = request.env(user=SUPERUSER_ID)['hr.employee'].browse(employee_id)
            
            if not employee.exists():
                return self._error_response(f'Empleado con ID {employee_id} no encontrado', status=404, error_code='EMPLOYEE_NOT_FOUND')
            
            employee_data = employee.get_employee_data_for_api()
            _logger.info(f"API Checadores: Consulta empleado {employee_id} desde {request.httprequest.remote_addr}. "
                f"Usuario JWT: {result.get('username')}" )
            
            return self._json_response({'status': 'success', 'timestamp': datetime.now().isoformat(), 'data': employee_data,})
        except Exception as e:
            _logger.error(f"API Checadores Error (employee/{employee_id}): {str(e)}", exc_info=True)
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
            from odoo import SUPERUSER_ID
            departments = request.env(user=SUPERUSER_ID)['hr.department'].search([])
            departments_data = [{'id': dept.id, 'name': dept.name, 'manager': dept.manager_id.name if dept.manager_id else '', 
                'parent_department': dept.parent_id.name if dept.parent_id else '', 'employee_count': dept.total_employee,} for dept in departments]
            return self._json_response({'status': 'success', 'timestamp': datetime.now().isoformat(), 'count': len(departments_data), 'data': departments_data,})
        except Exception as e:
            _logger.error(f"API Checadores Error (departments): {str(e)}", exc_info=True)
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
            from odoo import SUPERUSER_ID
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
