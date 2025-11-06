# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

class TipoZona(models.Model):
    _name = 'project.tipo.zona'
    _description = 'Tipos de Zona'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'code'

    name = fields.Char('Nombre del tipo', required=True, tracking=True)
    code = fields.Char('ID / Clave', tracking=True)
    description = fields.Char('Descripción', size=250)
    active = fields.Boolean('Activo', default=True)
    

class ZonaGeografica(models.Model):
    _name = 'project.zona.geografica'
    _description = 'Zonas Geográficas'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'code'

    name = fields.Char('Nombre de zona', required=True, tracking=True)
    code = fields.Char('Código de zona', size=10, tracking=True)
    tipo_zona_id = fields.Many2one('project.tipo.zona', string='Tipo de zona', ondelete='restrict', tracking=True)
    active = fields.Boolean('Activo', default=True)
    observaciones = fields.Text('Observaciones')


class Especialidad(models.Model):
    _name = 'project.especialidad'
    _description = 'Especialidades'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char('Nombre de especialidad', required=True, tracking=True)
    description = fields.Char('Descripción', size=300)
    clasificacion_id = fields.Many2one('project.technical.category', string='Categoría técnica', tracking=True)
    active = fields.Boolean('Activo', default=True)
    

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    zona_geografica_id = fields.Many2one('project.zona.geografica', string='Zona geográfica', tracking=True)
    partner_emisor_id = fields.Many2one('res.partner', string='Dependencia emisora', tracking=True)
    tipo_obra_id = fields.Many2one('project.type', string='Tipo de obra', tracking=True)
    especialidad_ids = fields.Many2many('project.especialidad', string='Especialidad(es) requerida(s)')
    monto_min = fields.Float('Monto mínimo')
    monto_max = fields.Float('Monto máximo')
    fecha_convocatoria = fields.Date('Fecha de convocatoria')
    fecha_limite_inscripcion = fields.Date('Fecha límite de inscripción')
    fecha_apertura = fields.Date('Fecha de apertura')
    convocatoria_pdf = fields.Binary('PDF de convocatoria', attachment=True)
    convocatoria_pdf_name = fields.Char('Nombre del archivo')

    """def write(self, vals):
        if 'stage_id' in vals:
            stage_to = self.env['crm.stage'].browse(vals['stage_id'])
            stage_from_names = set(self.mapped('stage_id.name'))
            if ('Nuevas Convocatorias' in stage_from_names) and stage_to and stage_to.name == 'Calificado':
                if not self.env.user.has_group('crm_convocatorias.group_convocatorias_autoriza_calificado'):
                    raise UserError('No tienes permiso para mover a 'Calificado'.')
        return super().write(vals)"""
