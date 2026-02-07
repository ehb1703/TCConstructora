# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import secrets
import logging

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    api_checadores_enabled = fields.Boolean(string='API Checadores Habilitada', config_parameter='api_checadores.enabled')
    api_checadores_username = fields.Char(string='Usuario API', config_parameter='api_checadores.username', help='Nombre de usuario para autenticación JWT')    
    api_checadores_jwt_secret = fields.Char(string='Clave JWT Secreta', config_parameter='api_checadores.jwt_secret')
    api_checadores_user_id = fields.Many2one('res.users', string='Usuario del API', compute='_compute_api_user', inverse='_inverse_api_user', store=False)
    api_checadores_user_active = fields.Boolean(string='Usuario Activo', related='api_checadores_user_id.active', readonly=True)
    api_checadores_password = fields.Char(string='Nueva Contraseña')

    @api.depends('api_checadores_username')
    def _compute_api_user(self):
        for record in self:
            if record.api_checadores_username:
                user = self.env['res.users'].search([('login', '=', record.api_checadores_username)], limit=1)
                record.api_checadores_user_id = user
            else:
                record.api_checadores_user_id = False
    
    def _inverse_api_user(self):
        for record in self:
            if record.api_checadores_user_id:
                record.api_checadores_username = record.api_checadores_user_id.login

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        jwt_secret = IrConfigParam.get_param('api_checadores.jwt_secret', '')
        if not jwt_secret:
            jwt_secret = secrets.token_urlsafe(32)
            IrConfigParam.set_param('api_checadores.jwt_secret', jwt_secret)
        
        res.update({'api_checadores_enabled': IrConfigParam.get_param('api_checadores.enabled', 'False').lower() == 'true',
            'api_checadores_username': IrConfigParam.get_param('api_checadores.username', ''), 'api_checadores_jwt_secret': jwt_secret,})
        return res


    def set_values(self):
        super(ResConfigSettings, self).set_values()
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        IrConfigParam.set_param('api_checadores.enabled', self.api_checadores_enabled)
        IrConfigParam.set_param('api_checadores.username', self.api_checadores_username or '')
        if self.api_checadores_jwt_secret:
            IrConfigParam.set_param('api_checadores.jwt_secret', self.api_checadores_jwt_secret)

    def action_regenerate_jwt_secret(self):
        self.ensure_one()
        new_secret = secrets.token_urlsafe(32)
        self.env['ir.config_parameter'].sudo().set_param('api_checadores.jwt_secret', new_secret)
        self.api_checadores_jwt_secret = new_secret
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Clave JWT Regenerada',
                'message': 'La clave JWT ha sido regenerada exitosamente.',
                'type': 'warning',
                'sticky': False,}}

    def action_update_api_password(self):
        self.ensure_one()
        if not self.api_checadores_user_id:
            raise UserError('No hay usuario configurado.')
        
        password = self.api_checadores_password
        if not password:
            raise UserError('Debe ingresar una contraseña.')
        
        if len(password) < 6:
            raise UserError('La contraseña debe tener al menos 6 caracteres.')
        
        try:
            # Actualizar contraseña del usuario
            self.api_checadores_user_id.sudo().write({'password': password})
            username = self.api_checadores_user_id.login
            
            # Primero intentar UPDATE
            self.env.cr.execute("UPDATE ir_config_parameter SET value = %s, write_uid = %s, write_date = NOW() WHERE key = 'api_checadores.password'", (
                password, self.env.uid))
            updated = self.env.cr.rowcount
            _logger.info(f"Registros actualizados: {updated}")
            
            if updated == 0:
                _logger.info("No existía, insertando nuevo registro...")
                self.env.cr.execute("""INSERT INTO ir_config_parameter (key, value, create_uid, create_date, write_uid, write_date)
                    VALUES ('api_checadores.password', %s, %s, NOW(), %s, NOW()) """, (password, self.env.uid, self.env.uid))
            
            # Verificar que se guardó
            self.env.cr.execute("SELECT value FROM ir_config_parameter WHERE key = 'api_checadores.password'")
            result = self.env.cr.fetchone()
            self.api_checadores_password = False
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Contraseña Actualizada',
                    'message': f'✓ Contraseña del usuario {username} actualizada\n✓ Parámetro del sistema actualizado\n\nVERIFIQUE en Parámetros del Sistema',
                    'type': 'success',
                    'sticky': True,}}
        except Exception as e:
            _logger.error(f"ERROR actualizando contraseña: {str(e)}")
            _logger.error(f"Detalles completos: {repr(e)}")
            raise UserError(f'Error al actualizar contraseña: {str(e)}')
    

    def action_open_api_user(self):
        self.ensure_one()
        if not self.api_checadores_user_id:
            raise UserError('No hay usuario configurado.')
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.users',
            'res_id': self.api_checadores_user_id.id,
            'view_mode': 'form',
            'view_id': self.env.ref('base.view_users_form').id,
            'target': 'new',}


    @api.constrains('api_checadores_enabled', 'api_checadores_username')
    def _check_api_configuration(self):
        for record in self:
            if record.api_checadores_enabled and not record.api_checadores_username:
                raise ValidationError('Debe ingresar un nombre de usuario para el API.')


class ResourceCalendarApiChecadores(models.Model):
    _inherit = 'resource.calendar'

    tolerance_minutes = fields.Integer(string='Min. Tolerancia', default=15, 
        help='Minutos de tolerancia permitidos para la entrada/salida. Este valor se envía a los sistemas de checadores externos.')
