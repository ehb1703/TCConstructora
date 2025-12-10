# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class projectType(models.Model):
    _name = 'project.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Tipo de Obra'
    _rec_name = 'code'

    code = fields.Char(string='Codigo del tipo de obra')
    name = fields.Char(string='Nombre')
    description = fields.Char(string='Descripción')
    normative_clas = fields.Selection(selection=[('na','No Aplica'), ('nom','NOM'), ('sct','SCT'), ('cfe','CFE'), ('conagua','CONAGUA')], 
        string='Clasificación Normativa', default='na')
    technicalcat_id = fields.Many2one('project.technical.category', string = 'Categoría Técnica')
    uom_id = fields.Many2one('uom.uom', string='Unidad de medida principal')
    docto_req_id = fields.Many2many('project.docsrequeridos', 'project_type_docsrequeridos_rel', 'project_req', string='Documentos Requeridos', 
        domain="[('model_id', '=', 'project.proyect')]")
    docto_noreq_id = fields.Many2many('project.docsrequeridos', 'project_type_docsnorequeridos_rel', 'projet_noreq', string='Documentos no Requeridos',
        domain="[('model_id', '=', 'project.proyect')]")
    observations = fields.Char(string='Observaciones')
    active = fields.Boolean(string='Activo', default=True, required=True)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.code} / {rec.name}'

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            domain = ['|', ('code', operator, name), ('name', operator, name)]
            recs = self.search(domain)
            recs.fetch(['display_name'])
            return [(rec.id, rec.display_name) for rec in recs]
        return super().name_search(name, args, operator, limit)


class projectTechnicalCategory(models.Model):
    _name = 'project.technical.category'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Categoría Técnica'
    _rec_name = 'name'

    name = fields.Char(string='Nombre')
    description = fields.Char(string='Descripción')
    active = fields.Boolean(string='Activo', default=True, required=True)    


class documentosRequeridos(models.Model):
    _name = 'project.docsrequeridos'
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    _description = 'Documentos'
    _rec_name = 'nombre_archivo'
   
    nombre_archivo = fields.Char(string='Valor', required=True, tracking=True)
    desc_archivo = fields.Char(string='Descripcion', tracking=True)
    model_id = fields.Many2one('ir.model', string='Modelo')
    etapa = fields.Selection(selection=[('tecnica','Propuesta Técnica'),('economica','Propuesta Económica')], string='Etapa')
    active = fields.Boolean(string='Activo', tracking=True, default=True, required=True)

    @api.constrains('nombre_archivo')
    def fnc_check_codigo(self):
        for x in self:
            if x.nombre_archivo:
                res = self.search([('nombre_archivo','=',x.nombre_archivo), ('id','!=',x.id)])
                if res:
                    raise UserError('Ya existe el archivo')

    @api.depends('nombre_archivo', 'desc_archivo')
    def _compute_display_name(self):
        for rec in self:
            if rec.nombre_archivo != rec.desc_archivo:
                rec.display_name = f'{rec.nombre_archivo} - {rec.desc_archivo}'
            else:
                rec.display_name = f'{rec.nombre_archivo}'


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
            rec.display_name = f'{rec.code} / {rec.name}' if rec.code else rec.name

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            domain = ['|', ('code', operator, name), ('name', operator, name)]
            recs = self.search(domain)
            recs.fetch(['display_name'])
            return [(rec.id, rec.display_name) for rec in recs]
        return super().name_search(name, args, operator, limit)


class Especialidad(models.Model):
    _name = 'project.especialidad'
    _description = 'Especialidades'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Nombre de especialidad', required=True, tracking=True)
    description = fields.Char(string='Descripción', size=300)
    clasificacion_id = fields.Many2one('project.technical.category', string='Categoría técnica', tracking=True)
    active = fields.Boolean(string='Activo', default=True)
    nivel_complejidad = fields.Selection(selection=[('alta','Alta'),('media','Media'),('baja','Baja')], string='Nivel de complejidad')
    requiere_validacion_externa = fields.Boolean('Requiere validación externa', tracking=True)


class crmStageOrigen(models.Model):
    _name = 'crm.lead.type'
    _description = 'Tipo de Venta'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Tipo', tracking=True)
    description = fields.Char(string='Descripción')
    bases = fields.Boolean(string='Bases', default=False)
    product_id = fields.Many2one('product.product', string='Concepto de pago')
    active = fields.Boolean(string='Activo', default=True)


class CrmAnalyst(models.Model):
    _name = 'crm.analyst'
    _description = 'Analistas'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    code = fields.Char('ID del analista', readonly=True, copy=False, tracking=True)
    origen = fields.Selection([('interno','Interno'),('externo','Externo')], default='interno', tracking=True)
    name = fields.Char(string='Nombre completo', compute='_compute_name', store=False)
    employee_id = fields.Many2one('hr.employee', string='Empleado interno', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Contacto externo', tracking=True)
    especialidad_id = fields.Many2many('project.especialidad', 'crm_analyst_esp', 'analyst_crm', string='Especialidad', tracking=True)
    years_experience = fields.Integer(string='Años de experiencia', tracking=True)
    quality_analysis = fields.Selection([('alto','Alto'),('medio','Medio'),('bajo','Bajo')], string='Calidad de análisis', tracking=True)
    quality_documental = fields.Selection([('alto','Alto'),('medio','Medio'),('bajo','Bajo')], string='Calidad documental', tracking=True)
    agility_operativa = fields.Selection([('alta','Alta'),('media','Media'),('baja','Baja')], string='Agilidad operativa', tracking=True)
    availability = fields.Selection([('disponible','Disponible'),('parcial','Parcial'),('no_disponible','No disponible')], string='Disponibilidad', tracking=True)
    compromiso_institucional = fields.Selection([('alto','Alto'),('medio','Medio'),('bajo','Bajo')], string='Compromiso institucional', tracking=True)
    proyectos_asignados = fields.Integer(string='Proyectos asignados actuales', tracking=True)
    ultima_evaluacion = fields.Date(string='Última evaluación de desempeño', tracking=True)
    observaciones = fields.Text(string='Observaciones', tracking=True)

    @api.depends('origen', 'employee_id', 'partner_id')
    def _compute_name(self):
        for record in self:
            if record.origen == 'interno':
                record.name = record.employee_id.name
            else:
                record.name = record.partner_id.name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'code' not in vals:
                seq = self.env['ir.sequence'].next_by_code('crm.analyst')
                vals['code'] = seq
        return super().create(vals_list)


class CrmRevertReason(models.Model):
    _name = 'crm.revert.reason'
    _description = 'Catálogo de motivos de reversión'
    _order = 'name'

    name = fields.Char(string='Motivo', required=True)
    description = fields.Char(string='Descripción')
    tipo = fields.Selection(selection=[('av','Avanzar etapa'),('rt','Retroceso de Etapa')],
        string='Tipo', default='rt')
    active = fields.Boolean(default=True)

class crmStageTypeBills(models.Model):
    _inherit = 'crm.stage'
    
    origen_ids = fields.Many2many('crm.lead.type', string='Tipo de venta permitido')
    email_ids = fields.Many2many('hr.employee', string='Distribución de correo')


class ModalidadContrato(models.Model):
    _name = 'project.modalidad.contrato'
    _description = 'Modalidad de Contrato'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'code'

    code = fields.Char(string='Codigo Modalidad', required=True, tracking=True, help='Identificador único para la modalidad (ej. M01, M02).')
    name = fields.Char(string='Nombre de modalidad', required=True, tracking=True, help='Nombre descriptivo (ej. Concurso Simplificado Sumario).')
    description = fields.Text(string='Descripción', tracking=True, help='Descripción detallada de la modalidad de contrato.')
    fundamento_legal = fields.Text(string='Fundamento legal', tracking=True, 
        help='Referencia al artículo o ley aplicable (ej. Ley de Obras Públicas y Servicios Relacionados).')
    active = fields.Boolean(string='Activo', default=True, help='Control para depuración y actualización del catálogo.')

    _sql_constraints = [('code_unique', 'unique(code)', 'El ID de modalidad debe ser único.'),]

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.code} - {rec.name}' if rec.code else rec.name

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            domain = ['|', ('code', operator, name), ('name', operator, name)]
            recs = self.search(domain + args, limit=limit)
            return [(rec.id, rec.display_name) for rec in recs]
        return super().name_search(name, args, operator, limit)
