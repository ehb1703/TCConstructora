# -*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import date

class CrmRefrendo(models.Model):
    _name = 'crm.refrendo'
    _description = 'Refrendos de Padrón de Proveedores'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'dependencia_id, razon_social_id'

    dependencia_id = fields.Many2one('res.partner', string='Dependencia', domain="[('is_company', '=', True)]", required=True, tracking=True)
    razon_social_id = fields.Many2one('res.company', string='Razón Social', required=True, tracking=True)
    linea_ids = fields.One2many('crm.refrendo.linea', 'refrendo_id', string='Historial de refrendos')
    disponible = fields.Boolean(string='Disponible', compute='_compute_ultimo_refrendo', store=True)
    fecha_refrendo = fields.Date(string='Fecha de Refrendo', compute='_compute_ultimo_refrendo', store=True)
    fecha_vigencia = fields.Date(string='Fecha de Vigencia', compute='_compute_ultimo_refrendo', store=True)
    responsable_id = fields.Many2one('res.partner', string='Responsable', domain="[('is_company', '=', False)]", compute='_compute_ultimo_refrendo', store=True)
    dias_vencimiento = fields.Integer(string='Días de vencimiento', compute='_compute_dias_vencimiento', store=True)
    estatus = fields.Char(string='Estatus', compute='_compute_estatus', store=True)
    observaciones = fields.Char(string='Observaciones', compute='_compute_ultimo_refrendo', store=True)

    _sql_constraints = [('dependencia_razon_uniq', 'unique(dependencia_id, razon_social_id)', 
        'Ya existe un refrendo para esta combinación de Dependencia y Razón Social.')]

    @api.depends('linea_ids', 'linea_ids.fecha_refrendo')
    def _compute_ultimo_refrendo(self):
        for rec in self:
            ultimo = rec.linea_ids.sorted('fecha_refrendo', reverse=True)[:1]
            if ultimo:
                rec.disponible = ultimo.disponible
                rec.fecha_refrendo = ultimo.fecha_refrendo
                rec.fecha_vigencia = ultimo.fecha_vigencia
                rec.responsable_id = ultimo.responsable_id
                rec.observaciones = ultimo.observaciones
            else:
                rec.disponible = False
                rec.fecha_refrendo = False
                rec.fecha_vigencia = False
                rec.responsable_id = False
                rec.observaciones = False

    @api.depends('fecha_vigencia')
    def _compute_dias_vencimiento(self):
        hoy = date.today()
        for rec in self:
            if rec.fecha_vigencia:
                rec.dias_vencimiento = (rec.fecha_vigencia - hoy).days
            else:
                rec.dias_vencimiento = 0

    @api.depends('dias_vencimiento')
    def _compute_estatus(self):
        min_dias = int(self.env['ir.config_parameter'].sudo().get_param(
            'project_extra.refrendo_min_dias', default=90))
        for rec in self:
            if rec.dias_vencimiento > min_dias:
                rec.estatus = 'VIGENTE'
            elif rec.dias_vencimiento > 0:
                rec.estatus = 'POR VENCER'
            else:
                rec.estatus = 'VENCIDO'

    def _send_alerta(self, registros):
        template = self.env.ref('project_extra.mail_tmpl_refrendo_alerta', raise_if_not_found=False)
        if not template:
            return

        for rec in registros:
            if not rec.responsable_id or not rec.responsable_id.email:
                continue
            
            template.send_mail(rec.id, force_send=True, email_values={'email_to': rec.responsable_id.email})
            rec.message_post(body='Alerta de vencimiento enviada a: %s' % rec.responsable_id.email)


    @api.model
    def cron_send_refrendo_alerta_minimo(self):
        min_dias = int(self.env['ir.config_parameter'].sudo().get_param('project_extra.refrendo_min_dias', default=90))
        registros = self.search([('dias_vencimiento', '=', min_dias)])
        self._send_alerta(registros)

    @api.model
    def cron_send_refrendo_alerta_10dias(self):
        registros = self.search([('dias_vencimiento', '=', 10)])
        self._send_alerta(registros)

    @api.model
    def cron_send_refrendo_alerta_vencimiento(self):
        registros = self.search([('dias_vencimiento', '=', 0)])
        self._send_alerta(registros)


class CrmRefrendoLinea(models.Model):
    _name = 'crm.refrendo.linea'
    _description = 'Historial de Refrendos'
    _order = 'fecha_refrendo desc'

    refrendo_id = fields.Many2one('crm.refrendo', string='Refrendo', required=True, ondelete='cascade')
    disponible = fields.Boolean(string='Disponible', default=True)
    fecha_refrendo = fields.Date(string='Fecha de Refrendo', required=True)
    fecha_vigencia = fields.Date(string='Fecha de Vigencia', required=True)
    responsable_id = fields.Many2one('res.partner', string='Responsable', domain="[('is_company', '=', False)]")
    observaciones = fields.Char(string='Observaciones')
    docto_vigencia = fields.Binary(string='Dto. Vigencia', attachment=True)
    docto_vigencia_name = fields.Char(string='Nombre documento vigencia')


class ResConfigSettingsRefrendo(models.TransientModel):
    _inherit = 'res.config.settings'

    refrendo_min_dias = fields.Integer(string='Mínimo de días de vigencia para envío de alertas', config_parameter='project_extra.refrendo_min_dias', default=90)
