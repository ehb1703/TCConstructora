# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class projectType(models.Model):
    _name = 'project.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Tipo de Obra'
    _rec_name = 'code'

    code = fields.Char(string='Codigo del tipo de obra')
    name = fields.Char(string='Nombre')
    description = fields.Char(string='Descripción')
    normative_clas = fields.Selection(selection=[('na','No Aplica'), ('nom','NOM'), ('sct','SCT'), ('cfe','CFE'), ('conagua','CONAGUA')], 
        string = 'Clasificación Normativa', default = 'na')
    technicalcat_id = fields.Many2one('project.technical.category', string = 'Categoría Técnica')
    uom_id = fields.Many2one('uom.uom', string='Unidad de medida principal')
    docto_req_id = fields.Many2many('project.docsrequeridos', 'project_type_docsrequeridos_rel', 'project_req', string='Documentos Requeridos')
    docto_noreq_id = fields.Many2many('project.docsrequeridos', 'project_type_docsnorequeridos_rel', 'projet_noreq', string='Documentos no Requeridos')
    observations = fields.Char(string='Observaciones')
    active = fields.Boolean(string='Activo', default=True, required=True)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.code} / {rec.name}'


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
    active = fields.Boolean(string='Activo', tracking=True, default=True, required=True)

    @api.constrains('nombre_archivo')
    def fnc_check_codigo(self):
        for x in self:
            if x.nombre_archivo:
                res = self.search([('nombre_archivo','=',x.nombre_archivo), ('id','!=',x.id)])
                if res:
                    raise UserError('Ya existe el archivo')


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


class Especialidad(models.Model):
    _name = 'project.especialidad'
    _description = 'Especialidades'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Nombre de especialidad', required=True, tracking=True)
    description = fields.Char(string='Descripción', size=300)
    clasificacion_id = fields.Many2one('project.technical.category', string='Categoría técnica', tracking=True)
    active = fields.Boolean(string='Activo', default=True)

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


class CrmRevertReason(models.Model):
    _name = 'crm.revert.reason'
    _description = 'Catálogo de motivos de reversión'
    _order = 'name'

    name = fields.Char(string='Motivo', required=True)
    description = fields.Char(string='Descripción')
    tipo = fields.Selection(selection=[('av','Avanzar etapa'),('rt','Retroceso de Etapa')],
        string='Tipo', default='rt')
    active = fields.Boolean(default=True)


class crmStageOrigen(models.Model):
    _inherit = 'crm.stage'
    
    origen_ids = fields.Many2many('crm.lead.type', string='Tipo de venta permitido')
    email_ids = fields.Many2many('hr.employee', string='Distribución de correo')