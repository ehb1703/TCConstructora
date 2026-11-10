# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class TipoContratista(models.Model):
    _name = 'partner.contractor.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Tipos de contratista'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True, tracking=True)
    docto_req_ids = fields.Many2many('project.docsrequeridos', 'partner_contractor_type_docreq_rel', 'type_id', 'docto_id', string='Documentos requeridos',
        domain="[('model_id.model', '=', 'res.partner')]", tracking=True)
    docto_noreq_ids = fields.Many2many('project.docsrequeridos', 'partner_contractor_type_docnoreq_rel', 'type_id', 'docto_id', string='Documentos no requeridos',
        domain="[('model_id.model', '=', 'res.partner')]", tracking=True)
    active = fields.Boolean(string='Activo', default=True, required=True, tracking=True)

    _sql_constraints = [('name_uniq', 'unique(name)', 'Ya existe un tipo de contratista con ese nombre.')]

    @api.constrains('docto_req_ids', 'docto_noreq_ids')
    def _check_documentos_repetidos(self):
        for rec in self:
            repetidos = rec.docto_req_ids & rec.docto_noreq_ids
            if repetidos:
                raise ValidationError('Un documento no puede ser requerido y no requerido a la vez: %s.' % ', '.join(repetidos.mapped('display_name')))


class ExpedienteDigital(models.Model):
    _name = 'partner.expediente.digital'
    _description = 'Expediente digital del contacto'
    _rec_name = 'docto_id'
    _order = 'requerido desc, id'

    partner_id = fields.Many2one('res.partner', string='Contacto', required=True, ondelete='cascade')
    requerido = fields.Boolean(string='Requerido')
    docto_id = fields.Many2one('project.docsrequeridos', string='Documento', required=True, domain="[('model_id.model', '=', 'res.partner')]")
    archivo = fields.Binary(string='Archivo', attachment=True)
    archivo_nombre = fields.Char(string='Nombre del archivo')
    # Como en el CRM (¿Generado?), pero se marca solo al subir el archivo y se desmarca si se quita
    generado = fields.Boolean(string='Generado', compute='_compute_generado', store=True)
    fecha_documento = fields.Date(string='Fecha del documento')
    vigencia = fields.Date(string='Vigencia', compute='_compute_vigencia', store=True,
        help='Fecha del documento más el intervalo y tiempo definidos en el catálogo de documentos.')

    @api.depends('archivo')
    def _compute_generado(self):
        for rec in self:
            rec.generado = bool(rec.archivo)

    @api.depends('fecha_documento', 'docto_id.intervalo', 'docto_id.tiempo')
    def _compute_vigencia(self):
        for rec in self:
            docto = rec.docto_id
            if rec.fecha_documento and docto.intervalo and docto.tiempo:
                rec.vigencia = rec.fecha_documento + relativedelta(**{docto.tiempo: docto.intervalo})
            else:
                rec.vigencia = False