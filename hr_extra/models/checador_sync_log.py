# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime

class ChecadorSyncLog(models.Model):
    _name = 'checador.sync.log'
    _description = 'Log de Sincronizaciones de Checadores'
    _order = 'sync_date desc'
    _rec_name = 'display_name'

    sync_date = fields.Datetime(string='Fecha de Sincronización', required=True, default=fields.Datetime.now, index=True)    
    sync_type = fields.Selection([('employees', 'Empleados'), ('attendances', 'Asistencias'), ('full', 'Completa')], 
        string='Tipo de Sincronización', default='employees', required=True)    
    device_id = fields.Char(string='ID Dispositivo', index=True, help='Identificador único del checador/dispositivo')
    records_synced = fields.Integer(string='Registros Sincronizados', default=0, help='Cantidad de registros enviados en esta sincronización')    
    status = fields.Selection([('success', 'Exitosa'), ('error', 'Error')], 
        string='Estado', default='success', required=True, index=True)
    ip_address = fields.Char(string='Dirección IP', help='IP del dispositivo que realizó la sincronización')    
    user_jwt = fields.Char(string='Usuario JWT', help='Usuario que autenticó la petición')    
    last_sync_reference = fields.Datetime(string='Referencia Última Sync', help='Fecha de la última sincronización usada como referencia')
    notes = fields.Text(string='Observaciones', help='Notas adicionales sobre la sincronización')
    display_name = fields.Char(string='Nombre', compute='_compute_display_name', store=True)

    @api.depends('sync_date', 'device_id', 'sync_type')
    def _compute_display_name(self):
        for record in self:
            device = record.device_id or 'Sin ID'
            date_str = record.sync_date.strftime('%Y-%m-%d %H:%M') if record.sync_date else ''
            record.display_name = f"{record.sync_type} - {device} - {date_str}"

    @api.model
    def get_last_successful_sync(self, sync_type='employees', device_id=None):
        # Obtiene la fecha de la última sincronización exitosa.
        domain = [('sync_type', '=', sync_type), ('status', '=', 'success'),]
        if device_id:
            domain.append(('device_id', '=', device_id))
        else:
            domain.append(('device_id', 'in', [False, '', None]))
        
        last_sync = self.search(domain, order='sync_date desc', limit=1)
        return last_sync.sync_date if last_sync else None


    @api.model
    def register_sync(self, sync_type='employees', device_id=None, records_count=0, status='success', ip_address=None, user_jwt=None, last_sync_ref=None, 
        notes=None):
        # Registra una nueva sincronización.
        return self.create({'sync_date': fields.Datetime.now(), 'sync_type': sync_type, 'device_id': device_id or '', 'records_synced': records_count,
            'status': status, 'ip_address': ip_address or '', 'user_jwt': user_jwt or '', 'last_sync_reference': last_sync_ref, 'notes': notes or '',})

    @api.model
    def cleanup_old_logs(self, days=90):
        # Elimina logs antiguos (más de X días).
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        old_logs = self.search([('sync_date', '<', cutoff_date)])
        count = len(old_logs)
        old_logs.unlink()
        return count