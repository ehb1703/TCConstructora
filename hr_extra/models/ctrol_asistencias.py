# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

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
    is_active = fields.Boolean(tring='Activo', default=True)
    createdAt = fields.Datetime(string='Fecha Creación', help='Fecha de creación en formato aaaa/mm/dd hh:mm', default=fields.Datetime.now)
    updatedAt = fields.Datetime(string='Fecha Actualización', help='Fecha de actualización en formato aaaa/mm/dd hh:mm', default=fields.Datetime.now)
    verification_status = fields.Selection([('auto', 'Automático'), ('manual_review', 'Revisión Manual'), ('approved', 'Aprobado'), ('rejected', 'Rechazado')], 
        string='Estado de Verificación')
    match_percentage = fields.Integer(string='Porcentaje de Coincidencia', help='Porcentaje de coincidencia biométrica (0-100)')
    log_message = fields.Text(string='Mensaje de Log', help='Mensaje o descripción del registro')    
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
            'employee_name': self.employee_name,
            'check_type': self.check_type,
            'photo_url': self.photo_url or '',
            'latitude': self.latitude,
            'longitude': self.longitude,
            'check_date': self.check_date.strftime('%Y-%m-%d %H:%M:%S') if self.check_date else '',
            'log_status': self.log_status,
            'lateness_time': self.lateness_time or '',
            'left_early_time': self.left_early_time or '',
            'is_active': self.is_active,
            'createdAt': self.createdAt.strftime('%Y/%m/%d %H:%M:%S') if self.createdAt else '',
            'updatedAt': self.updatedAt.strftime('%Y/%m/%d %H:%M:%S') if self.updatedAt else '',
            'verification_status': self.verification_status or '',
            'match_percentage': self.match_percentage or 0,
            'log_message': self.log_message or '',
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
