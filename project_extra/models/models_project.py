# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import config

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
        string = 'Clasificación Normativa', default = 'na')
    technicalcat_id = fields.Many2one('project.technical.category', string = 'Categoría Técnica')
    uom_id = fields.Many2one('uom.uom', string='Unidad de medida principal')
    docto_req_id = fields.Many2many('project.docsrequeridos', 'project_type_docsrequeridos_rel', 'project_req', string='Documentos Requeridos')
    docto_noreq_id = fields.Many2many('project.docsrequeridos', 'project_type_docsnorequeridos_rel', 'projet_noreq', string='Documentos no Requeridos')
    observations = fields.Char(string='Observaciones')
    active = fields.Boolean(string='Activo', default=True, required=True)


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

    @api.onchange('nombre_archivo')
    def _onchange_nombre_archivo(self):
        if self.nombre_archivo:
            self.nombre_archivo = self.nombre_archivo.upper()

    @api.constrains('nombre_archivo')
    def fnc_check_codigo(self):
        for x in self:
            if x.nombre_archivo:
                res = self.search([('nombre_archivo','=',x.nombre_archivo), ('id','!=',x.id)])
                if res:
                    raise UserError('Ya existe el archivo')


class projectObra(models.Model):
    _inherit = 'project.project'
    
    country_id = fields.Many2one('res.country', string='Pais')
    state_id = fields.Many2one('res.country.state', string='Estado')    
    city_id = fields.Many2one('res.municipalities', string='Municipio')
    street = fields.Char('Street')
    zip = fields.Char('Zip')
    partner_latitude = fields.Float('Geo Latitude', digits=(10, 7), default=0.0)
    partner_longitude = fields.Float('Geo Longitude', digits=(10, 7), default=0.0)
    date_localization = fields.Date(string='Geolocation Date')
    licitacion = fields.Char(string='Licitación')
    num_contrato = fields.Char(string='Número de contrato')
    documentos_ids =  fields.Many2many('project.documentation', string='Documentos')
    authorized_budget = fields.Float(string='Presupuesto Autorizado')
    cost_overrun = fields.Float(string='Sobrecosto')
    responsable_id = fields.Many2one('hr.employee', string='Responsable técnico')
    resident_ids = fields.One2many(comodel_name='project.residents', inverse_name='project_id', string='Residentes')
    type_id = fields.Many2one('project.type', string='Tipo de Obra')
    superficie = fields.Char(string='Superficie de la obra')
    centro = fields.Char(string='Centro de gravedad')
    tramo = fields.Char(string='Tramo')
    dependencia = fields.Char(string='Dependencia')
    bloque = fields.Char(string='Bloque')
    fianzas = fields.Char(string='Fianzas')

    @api.model
    def _geo_localize(self, street='', zip='', city='', state='', country=''):
        geo_obj = self.env['base.geocoder']
        search = geo_obj.geo_query_address(street=street, zip=zip, city=city, state=state, country=country)
        result = geo_obj.geo_find(search, force_country=country)
        if result is None:
            search = geo_obj.geo_query_address(city=city, state=state, country=country)
            result = geo_obj.geo_find(search, force_country=country)
        return result

    def geo_localize(self):
        if not self._context.get('force_geo_localize') and (self._context.get('import_file') \
                or any(config[key] for key in ['test_enable', 'test_file', 'init', 'update'])):
            return False
        partners_not_geo_localized = self.env['project.project']
        for partner in self.with_context(lang='en_US'):
            result = self._geo_localize(partner.street, partner.zip, partner.city_id.municipio, partner.state_id.name, partner.country_id.name)
            if result:
                partner.write({'partner_latitude': result[0], 'partner_longitude': result[1], 'date_localization': fields.Date.context_today(partner)})
            else:
                partners_not_geo_localized |= partner

        if partners_not_geo_localized:
            self.env.user._bus_send("simple_notification", 
                {'type': 'danger', 'title': _("Warning"),
                    'message': _('No match found for %(partner_names)s address(es).', partner_names=', '.join(partners_not_geo_localized.mapped('name')))})
        return True


    def cargar_docs(self):
        if self.type_id.docto_req_id or self.type_id.docto_noreq_id:
            if self.documentos_ids:
                for x in self.documentos_ids:
                    x.unlink()

            documentos = []
            for x in self.type_id.docto_req_id:
                documento = {'requerido':True, 'docto_id':x.id, 'project_id':self.id}
                documentos.append((0, 0, documento))

            for x in self.type_id.docto_noreq_id:
                documento = {'requerido':False, 'docto_id':x.id, 'project_id':self.id}
                documentos.append((0, 0, documento))
            
            self.write({'documentos_ids': documentos})
    

    def write(self, vals):
        if self.stage_id.name == 'Por hacer':
            stage_new = self.env['project.project.stage'].search([('id','=',vals.get('stage_id'))])
            if stage_new.name == 'Cancelada':
                raise ValidationError('Bajo que casos se puede realizar la cancelación de un proyecto')
            if stage_new.name == 'En progreso':
                for x in self.documentos_ids.filtered(lambda t: t.requerido):
                    if x.requerido:
                        if not x.filename or x.filename == '':
                            raise ValidationError('Existen archivos requeridos sin cargar. Favor de realizar la acción antes de continuar.')
        
        super(projectObra, self).write(vals)


class projectResidentes(models.Model):
    _name = 'project.residents'
    _description = 'Residentes de obra'

    project_id = fields.Many2one(comodel_name='', string='Proyecto', readonly=True)
    resident_id = fields.Many2one('hr.employee', string='Residente de Obra')
    active = fields.Boolean('Active', default=True, tracking=True)


class projectDocumentacion(models.Model):
    _name = 'project.documentation'
    _rec_name = 'docto_id'
    _description = 'Documentación'
    
    project_id = fields.Many2one('project.project', string='Proyecto')
    docto_id = fields.Many2one('project.docsrequeridos')
    requerido = fields.Boolean(string='Requerido')
    archivo = fields.Binary(string='Documento', attachment=True)
    filename = fields.Char(string='Filename')
