# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

class respartnerCurp(models.Model):
    _inherit = 'res.partner'

    curp = fields.Char(string='CURP')
    nacionalidad = fields.Char(string='Nacionalidad')
    is_supplier = fields.Boolean(string='Es proveedor')
    is_customer = fields.Boolean(string='Es cliente')
    is_afianzadora = fields.Boolean(string='Es afianzadora', default=False)
    clasification = fields.Selection(selection=[('gob','Gubernamental'),('priv','Privado'),('int','Interno')],
        string='Clasificación', default='gob')
    typesupplier_id = fields.Many2one('partner.type.supplier', string='Tipo de Proveedor', tracking=True)
    classupplier_id = fields.Many2one('partner.classification.supplier', string='Clasificación del Proveedor', tracking=True)
    area_em = fields.Char(string='Zona Geográfica', tracking=True)
    soporte_ids = fields.Many2many(comodel_name='ir.attachment', string="Documentos fiscales")
    responsable_id = fields.Many2one('res.partner', string='Responsable', tracking=True)
    apaterno = fields.Char(string='Apellido Paterno', tracking=True)
    amaterno = fields.Char(string='Apellido Materno', tracking=True)
    nombre = fields.Char(string='Nombre(s)', tracking=True)
    country_id = fields.Many2one('res.country', string='País', default=lambda self: self.env.company.country_id)

    @api.model
    def default_get(self, fields_list):
        """ Override para forzar las cuentas contables correctas al crear un nuevo contacto. 
            Odoo 18 busca por ID ASC lo que hace que tome cuentas obsoletas con ID menor. """
        res = super().default_get(fields_list)
        if 'property_account_receivable_id' in fields_list:
            account_rec = self.env['account.account'].search([('account_type', '=', 'asset_receivable'), ('deprecated', '=', False), 
                ('code', 'not ilike', '.00.')], limit=1, order='code')
            if account_rec:
                res['property_account_receivable_id'] = account_rec.id
            else:
                _logger.warning("contact_extra: No se encontró la cuenta para default receivable.")
        if 'property_account_payable_id' in fields_list:
            account_pay = self.env['account.account'].search([('account_type', '=', 'liability_payable'), ('deprecated', '=', False), 
                ('code', 'not ilike', '.00.')], limit=1, order='code')
            if account_pay:
                res['property_account_payable_id'] = account_pay.id
            else:
                _logger.warning("contact_extra: No se encontró la cuenta para default payable.")
        return res

    @api.constrains('curp')
    def _check_curp(self):
        for record in self:
            if record.curp:
                if len(record.curp) != 18:
                    raise ValidationError(_('El CURP debe de tener 18 caracteres'))

    @api.onchange('apaterno', 'amaterno', 'nombre')
    def onchange_name(self):
        name, paterno, materno, nombre = '', '', '', ''
        if not self.is_company:
            if self.apaterno:
                paterno = self.apaterno
            if self.amaterno:
                materno = self.amaterno
            if self.nombre:
                nombre = self.nombre
            self.name = nombre + ' ' + paterno + ' ' + materno
        else:
            self.name = self.nombre

    def write(self, values):
        if any(field in values for field in ['name']):
            if values.get('name') != self.name:
                empleado = self.env['hr.employee'].search([('work_contact_id', '=', self.id)])
                if empleado:
                    empleado.update({'name': values.get('name'), 'legal_name': values.get('name')})
                    empleado.resource_id.update({'name': values.get('name')})
        return super().write(values)


class rescompanyContacts(models.Model):
    _inherit = 'res.company'
    
    incorporation_date = fields.Date(string='Fecha de constitución')
    bank_account_id = fields.Many2one('res.partner.bank', string='Cuenta Bancaria Principal', tracking=True, ondelete='restrict', copy=False)
    bank_accounts_id = fields.Many2one('res.partner.bank', string='Cuenta Bancaria Secundaria', tracking=True, ondelete='restrict', copy=False)
        #check_company=True, domain="[('partner_id','=', partner_id.company_id.partner_id)]")
    responsable_id = fields.Many2one('res.partner', string='Responsable', tracking=True)
    taxpayer_id = fields.Many2one('company.type.taxpayer', string='Tipo de Contribuyente', tracking=True)
    area_em = fields.Char(string='Zona Geográfica', tracking=True)


class companyLegalRepresentative(models.Model):
    _name = 'company.legal.representative'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'representante_id'
    _description = 'Representante Legal'

    company_id = fields.Many2one('res.company', string='Empresa')
    representante_id = fields.Many2one('res.partner', string='Nombre', tracking=True)
    vat = fields.Char(string='RFC', compute='_compute_representante', readonly=True)
    curp = fields.Char(string='CURP', compute='_compute_representante', readonly=True)
    cargo = fields.Selection(selection=[('rp','Representante Legal'), ('dg','Director General'), ('au','Administrador Unico')],
        string='Cargo', default='rp', tracking=True)
    appointment_date = fields.Date(string='Fecha de nombramiento')
    term_date = fields.Date(string='Vigencia del cargo')
    legal_powers = fields.Char(string='Facultades legales')
    notario = fields.Char(string='Instrumento legal que respalda')
    soporte_ids = fields.Many2many(comodel_name='ir.attachment', string="Documentación soporte")
    observaciones = fields.Char(string='Observaciones')
    state = fields.Selection(selection=[('activo','Activo'), ('sustituido','Sustituido'), ('revocado','Revocado')],
        string='Estado Actual', default='activo', tracking=True)

    @api.onchange('representante_id')
    def _compute_representante(self):
        for record in self:
            if record.representante_id.vat != None:
                record.vat = record.representante_id.vat
            if record.representante_id.curp != None:
                record.curp = record.representante_id.curp

    def action_sustituir(self):
        self.state = 'sustituido'

    def action_revocar(self):
        self.state = 'revocado'


class companyPartners(models.Model):
    _name = 'company.partners'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'partner_id'
    _description = 'Socios'

    company_id = fields.Many2one('res.company', string='Empresa', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Nombre', tracking=True)
    vat = fields.Char(string='RFC', compute='_compute_partners', readonly=True)
    curp = fields.Char(string='CURP', compute='_compute_partners', readonly=True)
    is_company = fields.Char(string='Tipo de persona', compute='_compute_partners', readonly=True)
    nacionalidad = fields.Char(string='Nacionalidad', compute='_compute_partners', readonly=True)
    porcentaje = fields.Float(string='porcentaje de participación')
    appointment_date = fields.Date(string='Fecha de nombramiento')
    soporte_ids = fields.Many2many(comodel_name='ir.attachment', string="Documentación soporte")
    observaciones = fields.Char(string='Observaciones')
    state = fields.Selection(selection=[('activo','Activo'), ('inactivo','Inactivo'), ('retirado','Retirado')],
        string='Estado Actual', default='activo', tracking=True)

    @api.onchange('partner_id')
    def _compute_partners(self):
        for record in self:
            if record.partner_id.vat != None:
                record.vat = record.partner_id.vat
            if record.partner_id.curp != None:
                record.curp = record.partner_id.curp
            if record.partner_id.is_company != None:
                record.is_company = record.partner_id.is_company
            if record.partner_id.nacionalidad != None:
                record.nacionalidad = record.partner_id.nacionalidad

    def action_inactivar(self):
        self.state = 'inactivo'

    def action_retirar(self):
        self.state = 'retirado'


class companyLegalProxy(models.Model):
    _name = 'company.legal.proxy'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'partner_id'
    _description = 'Apoderado legal'

    company_id = fields.Many2one('res.company', string='Empresa', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Nombre', tracking=True)
    vat = fields.Char(string='RFC', compute='_compute_partners', readonly=True)
    curp = fields.Char(string='CURP', compute='_compute_partners', readonly=True)
    power = fields.Selection(selection=[('gral','General'), ('admin','Administrativo'), ('judicial','Judicial'), ('especial','Especial')],
        string='Tipo de poder', default='gral', tracking=True)
    faculties = fields.Char(string='Alcance del poder')
    grant_date = fields.Date(string='Fecha de otorgamiento')
    term_date = fields.Date(string='Vigencia del poder')
    notario = fields.Char(string='Instrumento legal que respalda')
    soporte_ids = fields.Many2many(comodel_name='ir.attachment', string="Documentación soporte")
    observaciones = fields.Char(string='Observaciones')
    state = fields.Selection(selection=[('activo','Activo'), ('inactivo','Inactivo'), ('vencido','Vencido')],
        string='Estado Actual', default='activo', tracking=True)

    @api.onchange('partner_id')
    def _compute_partners(self):
        for record in self:
            if record.partner_id.vat != None:
                record.vat = record.partner_id.vat
            if record.partner_id.curp != None:
                record.curp = record.partner_id.curp

    def action_inactivar(self):
        self.state = 'inactivo'

    def action_vencer(self):
        self.state = 'vencido'


class companyPublicRecord(models.Model):
    _name = 'company.public.record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'folio'
    _description = 'Registro Público'

    company_id = fields.Many2one('res.company', string='Empresa', tracking=True)
    folio = fields.Char(string='Nombre', tracking=True)
    registration_date = fields.Date(string='Fecha de Registro')
    type = fields.Selection(
        selection=[('const','Constitución de Sociedades mercantiles (SA. , S. de R.L., etc.)'), ('insc','Inscripción de poderes notariales'),
            ('mod','Modificaciones estatutarias (cambio de domicilio, objeto social, capital)'), ('compra','Compra-venta de inmuebles'),
            ('fusion','Fusión, escisión o liquidación de sociedades'), ('cont', 'Inscripción de contratos de garantía (hipotecas, fideicomisos).')],
        string='Tipo de trámite', tracking=True)
    docto_ids = fields.Many2many(comodel_name='ir.attachment', string="Actas")
    observaciones = fields.Char(string='Observaciones')
    active = fields.Boolean(string='Activo', default=True)


class companyAssembly(models.Model):
    _name = 'company.assembly'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'folio'
    _description = 'Asamblea'

    company_id = fields.Many2one('res.company', string='Empresa', tracking=True)
    folio = fields.Char(string='Nombre', tracking=True)
    registration_date = fields.Date(string='Fecha de Registro')
    type = fields.Selection(
        selection=[('const','Constitución de la sociedad o asociación (asamblea constitutiva).'), ('aprob','Aprobación de estados financieros.'),
            ('mod','Modificación de estatutos sociales.'), ('nomb','Nombramiento o remoción de administradores, comisarios o representantes.')],
        string='Tipo de trámite', tracking=True)
    docto_ids = fields.Many2many(comodel_name='ir.attachment', string="Actas")
    observaciones = fields.Char(string='Observaciones')
    active = fields.Boolean(string='Activo', default=True)


class companyEmployerRegistration(models.Model):
    _name = 'company.employer.registration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'folio'
    _description = 'Registro Patronal'

    company_id = fields.Many2one('res.company', string='Empresa', tracking=True)
    folio = fields.Char(string='Nombre', tracking=True)
    registration_date = fields.Date(string='Fecha de Registro')
    type = fields.Selection(
        selection=[('alta','Alta como patrón ante el IMSS.'), ('inicio','Inicio de operaciones con personal subordinado.'),
        ('const','Constitución de una empresa con empleados.'), ('reg','Registro de sucursales o centros de trabajo adicionales.'),
        ('mod','Modificación de datos patronales (domicilio, razón social, régimen fiscal).')],
        string='Tipo de trámite', tracking=True)
    docto_ids = fields.Many2many(comodel_name='ir.attachment', string="Actas")
    observaciones = fields.Char(string='Observaciones')
    active = fields.Boolean(string='Activo', default=True)


class companyCommissar(models.Model):
    _name = 'company.commissar'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'partner_id'
    _description = 'Comisario'

    company_id = fields.Many2one('res.company', string='Empresa', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Nombre', tracking=True)
    vat = fields.Char(string='RFC', compute='_compute_partners', readonly=True)
    curp = fields.Char(string='CURP', compute='_compute_partners', readonly=True)
    observaciones = fields.Char(string='Observaciones')
    active = fields.Boolean(string='Activo', default=True)

    @api.onchange('partner_id')
    def _compute_partners(self):
        for record in self:
            if record.partner_id.vat != None:
                record.vat = record.partner_id.vat
            if record.partner_id.curp != None:
                record.curp = record.partner_id.curp
