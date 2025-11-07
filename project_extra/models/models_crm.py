# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

class TipoZona(models.Model):
    _name = 'project.tipo.zona'
    _description = 'Tipos de Zona'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'code'

    name = fields.Char(string='Nombre del tipo', required=True, tracking=True)
    code = fields.Char(string='ID / Clave', tracking=True)
    description = fields.Char(string='Descripción', size=250)
    active = fields.Boolean(string='Activo', default=True)
    

class ZonaGeografica(models.Model):
    _name = 'project.zona.geografica'
    _description = 'Zonas Geográficas'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'code'

    name = fields.Char(string='Nombre de zona', required=True, tracking=True)
    code = fields.Char(string='Código de zona', size=10, tracking=True)
    tipo_zona_id = fields.Many2one('project.tipo.zona', string='Tipo de zona', ondelete='restrict', tracking=True)
    active = fields.Boolean(string='Activo', default=True)
    observaciones = fields.Text(string='Observaciones')

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.code} / {rec.name}"


class Especialidad(models.Model):
    _name = 'project.especialidad'
    _description = 'Especialidades'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Nombre de especialidad', required=True, tracking=True)
    description = fields.Char(string='Descripción', size=300)
    clasificacion_id = fields.Many2one('project.technical.category', string='Categoría técnica', tracking=True)
    active = fields.Boolean(string='Activo', default=True)
    

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    zona_geografica_id = fields.Many2one('project.zona.geografica', string='Zona geográfica', tracking=True)
    partner_emisor_id = fields.Many2one('res.partner', string='Dependencia emisora', tracking=True)
    tipo_obra_id = fields.Many2one('project.type', string='Tipo de obra', tracking=True)
    especialidad_ids = fields.Many2many('project.especialidad', string='Especialidad(es) requerida(s)')
    monto_min = fields.Float(string='Monto mínimo')
    monto_max = fields.Float(string='Monto máximo')
    fecha_convocatoria = fields.Date(string='Fecha de convocatoria')
    fecha_limite_inscripcion = fields.Date(string='Fecha límite de inscripción')
    fecha_apertura = fields.Date(string='Fecha de apertura')
    convocatoria_pdf = fields.Binary(string='PDF de convocatoria', attachment=True)
    convocatoria_pdf_name = fields.Char(string='Nombre del archivo')
    origen_id = fields.Many2one('crm.lead.type', string='Tipo')
    origen_name = fields.Char(string='Tipo nombre', compute='_compute_bases' )
    req_bases = fields.Boolean(string='Requiere pago de bases', compute='_compute_bases')
    tipo_obra_ok = fields.Boolean('Tipo de obra cumple', tracking=True)
    dependencia_ok = fields.Boolean('Dependencia emisora cumple', tracking=True)
    capital_ok = fields.Boolean('Capital contable cumple', tracking=True)
    oc_id = fields.Many2one('purchase.order', string='Ordenes de compra relacionada')

    @api.onchange('origen_id')
    def _compute_bases(self):
        for record in self:
            record.req_bases = record.origen_id.bases
            record.origen_name = record.origen_id.name

    def action_generar_orden(self):
        raise UserError('Pendiente de hacer el proceso completo')
