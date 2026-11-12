# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import config
import ast
import logging

_logger = logging.getLogger(__name__)

class projectBlocks(models.Model):
    _name = 'project.blocks'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'block_id'
    _description = 'Bloques del proyecto'

    def _compute_project_count(self, count_field='project_count'):
        count_fields = {fname for fname in self._fields if 'count' in fname}
        if count_field not in count_fields:
            raise ValueError(f"Parameter 'count_field' can only be one of {count_fields}, got {count_field} instead.")
        domain = [('block_id', 'in', self.ids)] #, ('display_in_project', '=', True)
        tasks_count_by_project = dict(self.env['project.project'].with_context(active_test=any(project.active for project in self))._read_group(
            domain, ['block_id'], ['__count']))
        for project in self:
            project.update({count_field: tasks_count_by_project.get(project, 0)})

    block_id = fields.Many2one('project.bloque', string='Bloque', readonly=True, copy=False)
    label_proj = fields.Char(string='Use Project as', default=lambda s: s.env._('Contrato'), translate=True, help='Name used to refer to the project of your block')
    project_ids = fields.One2many(comodel_name='project.project', inverse_name='block_id', string='Proyecto')
    project_count = fields.Integer(compute='_compute_project_count', string='Contratos')
    active = fields.Boolean(default=True)

    def action_view_tasks(self):
        action = self.env['ir.actions.act_window'].with_context(active_id=self.id)._for_xml_id('open_view_project_filter')
        #action['display_name'] = self.block_id.name
        context = action['context'].replace('active_id', str(self.id))
        context = ast.literal_eval(context)
        context.update({
            'create': self.active,
            'active_test': self.active
            })
        action['context'] = context
        return action


class projectObra(models.Model):
    _inherit = 'project.project'
    
    block_id = fields.Many2one('project.blocks', string='Bloque', readonly=True)
    lead_id = fields.Many2one('crm.lead', string='Oportunidad/Licitación', readonly=True, copy=False)
    orden_trabajo = fields.Char(string='Orden de trabajo', readonly=True)
    proj_fecha_adjudicacion = fields.Date(string='Fecha de adjudicación', readonly=True)
    proj_dias = fields.Integer(string='Días', readonly=True)
    proj_anticipo_porcentaje = fields.Integer(string='% de anticipo', readonly=True)
    proj_importe_anticipo = fields.Float(string='Importe anticipo', readonly=True)
    fecha_inicio_obra = fields.Date(string='Fecha inicio', readonly=True, compute='_compute_fecha_inicio_obra', store=True)
    fecha_fin_obra = fields.Date(string='Fecha fin')
    normatividad_id = fields.Many2one('project.normatividad', string='Normatividad', 
        help='Marco normativo aplicable a la obra')
    contrato_a_id = fields.Many2one('project.modalidad.precios', string='Contrato a', 
        help='Modalidad de precios del contrato')
    direccion_gral_ejecutora_id = fields.Many2one('project.direccion.ejecutora', string='Dirección General Ejecutora', 
        help='Unidad ejecutora responsable de la obra')
    modalidad_contratacion_id = fields.Many2one('project.modalidad.contrato', string='Modalidad de contratación', readonly=True)
    proj_fecha_apertura = fields.Date(string='Fecha de apertura', readonly=True)
    proj_rupc_siop = fields.Char(string='RUPC. SIOP', readonly=True)
    proj_es_siop = fields.Boolean(string='Es SIOP', readonly=True)
    proj_sancion_atraso = fields.Boolean(string='Sanción por atraso', readonly=True)
    proj_ret_5_millar = fields.Boolean(string='Ret. 5 al millar', readonly=True)
    proj_ret_2_millar = fields.Boolean(string='Ret. 2 al millar', readonly=True)
    country_id = fields.Many2one('res.country', string='Pais')
    state_id = fields.Many2one('res.country.state', string='Estado')    
    city_id = fields.Many2one('res.municipalities', string='Municipio')
    street = fields.Char(string='Street')
    between_streets = fields.Char(string='Entre Calles')
    col = fields.Char(string='Colonia')
    zip = fields.Char(string='Zip')
    partner_latitude = fields.Float(string='Geo Latitude', digits=(10, 7), default=0.0)
    partner_longitude = fields.Float(string='Geo Longitude', digits=(10, 7), default=0.0)
    date_localization = fields.Date(string='Geolocation Date')
    licitacion = fields.Char(string='No. de Proceso')
    num_contrato = fields.Char(string='Número de contrato')
    documentos_ids = fields.Many2many('project.documentation', string='Documentos')
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

    @api.depends('lead_id', 'lead_id.fecha_firma')
    def _compute_fecha_inicio_obra(self):
        # Toma la fecha de firma del contrato en la etapa Ganado del CRM
        for project in self:
            if project.lead_id and project.lead_id.fecha_firma:
                project.fecha_inicio_obra = project.lead_id.fecha_firma
            else:
                project.fecha_inicio_obra = False

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
                        if not x.generado:
                            raise ValidationError('Existen archivos requeridos sin cargar. Favor de realizar la acción antes de continuar.')
        
        super(projectObra, self).write(vals)


class projectResidentes(models.Model):
    _name = 'project.residents'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Residentes de obra'

    project_id = fields.Many2one('project.project', string='Proyecto', readonly=True)
    resident_id = fields.Many2one('hr.employee', string='Residente de Obra')
    active = fields.Boolean('Active', default=True, tracking=True)


class projectDocumentacion(models.Model):
    _name = 'project.documentation'
    _rec_name = 'docto_id'
    _description = 'Documentación'
    
    project_id = fields.Many2one('project.project', string='Proyecto')
    docto_id = fields.Many2one('project.docsrequeridos')
    requerido = fields.Boolean(string='Requerido')
    generado = fields.Boolean(string='Generado')
