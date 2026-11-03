# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.models import Command


class DocumentosRequeridosVigencia(models.Model):
    _inherit = 'project.docsrequeridos'

    intervalo = fields.Integer(string='Intervalo', tracking=True, help='Cada cuánto pierde vigencia el documento. Si se deja vacío, el documento no vence.')
    tiempo = fields.Selection(selection=[('days', 'Días'), ('weeks', 'Semanas'), ('months', 'Meses'), ('years', 'Años')], string='Tiempo', tracking=True)

    @api.constrains('intervalo', 'tiempo')
    def _check_vigencia(self):
        for rec in self:
            if rec.intervalo < 0:
                raise ValidationError('El intervalo de vigencia no puede ser negativo.')
            if rec.intervalo and not rec.tiempo:
                raise ValidationError(f'Indique el tiempo (días, semanas, meses o años) del intervalo del documento "{rec.display_name}".')


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
    fecha_documento = fields.Date(string='Fecha del documento')
    vigencia = fields.Date(string='Vigencia', compute='_compute_vigencia', store=True,
        help='Fecha del documento más el intervalo y tiempo definidos en el catálogo de documentos.')

    @api.depends('fecha_documento', 'docto_id.intervalo', 'docto_id.tiempo')
    def _compute_vigencia(self):
        for rec in self:
            docto = rec.docto_id
            if rec.fecha_documento and docto.intervalo and docto.tiempo:
                rec.vigencia = rec.fecha_documento + relativedelta(**{docto.tiempo: docto.intervalo})
            else:
                rec.vigencia = False


class ResPartnerExpediente(models.Model):
    _inherit = 'res.partner'

    tipo_contratista = fields.Many2one('partner.contractor.type', string='Tipo de contratista', tracking=True)
    expediente_digital = fields.One2many('partner.expediente.digital', 'partner_id', string='Expediente digital')
    expediente_completo = fields.Boolean(string='Expediente completo', compute='_compute_expediente_completo', store=True,
        help='Se marca cuando todos los documentos requeridos del tipo de contratista tienen archivo cargado.')

    @api.depends('tipo_contratista', 'expediente_digital.requerido', 'expediente_digital.archivo')
    def _compute_expediente_completo(self):
        for rec in self:
            requeridos = rec.expediente_digital.filtered('requerido')
            rec.expediente_completo = bool(rec.tipo_contratista) and all(requeridos.mapped('archivo'))

    def _sincronizar_expediente(self):
        """Alinea las líneas del expediente con el tipo de contratista: agrega los documentos que faltan y quita los que ya no aplican y no tienen archivo.
        Un documento con archivo cargado nunca se borra; si ya no aplica queda como no requerido."""
        for rec in self:
            tipo = rec.tipo_contratista
            deseados = {d.id: True for d in tipo.docto_req_ids}
            deseados.update({d.id: False for d in tipo.docto_noreq_ids if d.id not in deseados})
            comandos = []
            for linea in rec.expediente_digital:
                if linea.docto_id.id in deseados:
                    comandos.append(Command.update(linea.id, {'requerido': deseados.pop(linea.docto_id.id)}))
                elif linea.archivo:
                    comandos.append(Command.update(linea.id, {'requerido': False}))
                else:
                    comandos.append(Command.delete(linea.id))
            comandos += [Command.create({'docto_id': docto_id, 'requerido': requerido}) for docto_id, requerido in deseados.items()]
            if comandos:
                rec.expediente_digital = comandos

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        partners.filtered('tipo_contratista')._sincronizar_expediente()
        return partners

    def write(self, vals):
        res = super().write(vals)
        if 'tipo_contratista' in vals:
            self._sincronizar_expediente()
        return res
