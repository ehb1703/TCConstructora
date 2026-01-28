# -*- coding: utf-8 -*-
import secrets
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

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
            'api_checadores_username': IrConfigParam.get_param('api_checadores.username', 'api_checadores'),
            'api_checadores_jwt_secret': jwt_secret,})
        return res


    def set_values(self):
        super(ResConfigSettings, self).set_values()
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        IrConfigParam.set_param('api_checadores.enabled', self.api_checadores_enabled)
        IrConfigParam.set_param('api_checadores.username', self.api_checadores_username or 'api_checadores')
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

    def action_create_api_user(self):
        self.ensure_one()
        if not self.api_checadores_enabled:
            raise UserError('Debe habilitar el API antes de crear un usuario.')
        
        base_login = 'api_checadores'
        login = base_login
        counter = 1
        
        while self.env['res.users'].search([('login', '=', login)], limit=1):
            login = f"{base_login}_{counter}"
            counter += 1
        
        password = secrets.token_urlsafe(16)
        hr_user_group = self.env.ref('hr.group_hr_user', raise_if_not_found=False)
        base_user_group = self.env.ref('base.group_user', raise_if_not_found=False)
        user_vals = {'name': 'API Checadores TC', 'login': login, 'email': f'{login}@empresa.local', 'password': password, 'active': True,}
        groups_to_add = []
        if base_user_group:
            groups_to_add.append((4, base_user_group.id))
        if hr_user_group:
            groups_to_add.append((4, hr_user_group.id))
        
        if groups_to_add:
            user_vals['groups_id'] = groups_to_add
        
        user = self.env['res.users'].create(user_vals)
        self.api_checadores_username = login
        self.api_checadores_user_id = user
        self.api_checadores_password = password
        
        self.env['ir.config_parameter'].sudo().set_param('api_checadores.username', login)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Usuario Creado',
                'message': f'Usuario: {login}\nContraseña: {password}\n\nGuarde estas credenciales.',
                'type': 'success',
                'sticky': True,}}


    def action_update_api_password(self):
        self.ensure_one()
        if not self.api_checadores_user_id:
            raise UserError('No hay usuario configurado.')
        
        if not self.api_checadores_password:
            raise UserError('Debe ingresar una contraseña.')
        
        if len(self.api_checadores_password) < 8:
            raise UserError('La contraseña debe tener al menos 8 caracteres.')
        
        self.api_checadores_user_id.sudo().write({'password': self.api_checadores_password})
        username = self.api_checadores_user_id.login
        self.api_checadores_password = False
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Contraseña Actualizada',
                'message': f'La contraseña del usuario {username} ha sido actualizada.',
                'type': 'success',
                'sticky': False,}}
    

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
                raise ValidationError('Debe configurar un usuario antes de habilitar el API.')
            
            if record.api_checadores_enabled and record.api_checadores_username:
                user = self.env['res.users'].search([('login', '=', record.api_checadores_username)], limit=1)
                if not user:
                    raise ValidationError(f'El usuario "{record.api_checadores_username}" no existe.')
                
                if not user.active:
                    raise ValidationError(f'El usuario "{record.api_checadores_username}" está inactivo.')


class ResourceCalendarApiChecadores(models.Model):
    _inherit = 'resource.calendar'

    tolerance_minutes = fields.Integer(string='Min. Tolerancia', default=15, 
        help='Minutos de tolerancia permitidos para la entrada/salida. Este valor se envía a los sistemas de checadores externos.')
