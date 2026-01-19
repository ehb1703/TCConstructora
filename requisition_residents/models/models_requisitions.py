# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class requisitionResidents(models.Model):
    _name = 'requisition.residents'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Requisiciones de Residentes de Obras'

    name = fields.Char(string='Nombre')
    finicio = fields.Date(string='Periodo Inicial')
    ffinal = fields.Date(string='Periodo Final')
    project_id = fields.Many2one('project.project', string='Obra')
    employee_id = fields.Many2one('hr.employee', string='Responsable')
    company_id = fields.Many2one('res.company', string='Empresa', tracking=True)
    amount_untaxed = fields.Float(string='Importe sin IVA', compute='_compute_amount', store=True, readonly=True, tracking=True)
    amount_tax = fields.Float(string='Impuestos', compute='_compute_amount', store=True, readonly=True)
    amount_total = fields.Float(string='Total', compute='_compute_amount', store=True, readonly=True)
    state = fields.Selection(selection=[('draft','Borrador'), ('send','Enviado'), ('aprobado','Aprobado')],
        string='Estatus', default='draft', tracking=True)
    line_ids = fields.One2many('requisition.residents.line', 'req_id', string='Resumen')
    destajo_ids = fields.One2many('requisition.destajo', 'req_id', string='Destajo')
    acarreo_ids = fields.One2many('requisition.acarreos', 'req_id', string='Acarreos')
    campamento_ids = fields.One2many('requisition.campamentos', 'req_id', string='Campamentos')
    maquinaria_ids = fields.One2many('requisition.maquinaria', 'req_id', string='Maquinaria')
    cash_ids = fields.One2many('requisition.cash', 'req_id', string='Caja Chica')
    nom_ids = fields.One2many('requisition.nomina', 'req_id', string='Nomina')

    @api.depends('line_ids.amount_untaxed', 'line_ids.amount_tax', 'line_ids.amount_total')
    def _compute_amount(self):
        for req in self:
            total_untaxed, total_tax, total = 0.0, 0.0, 0.0
            for line in req.line_ids:
                total_untaxed += line.amount_untaxed
                total_tax += line.amount_tax
                total += line.amount_total
            req.amount_untaxed = total_untaxed
            req.amount_tax = total_tax
            req.amount_total = total

    @api.onchange('finicio', 'ffinal')
    def validar_fechas(self):
        if self.finicio and self.ffinal:
            dias = self.ffinal - self.finicio
            if dias.days > 6:
                raise ValidationError('El periodo seleccionado es mayor a una semana.')

    def action_resumen(self):
        req_lines = []
        if self.cash_ids:
            total = 0
            relacion = ''
            for rec in self.cash_ids:
                if rec.amount != 0:
                    total += rec.amount
                    relacion = relacion + str(rec.id) + ','
            if relacion != '':
                lines = {'category': 'Caja Chica', 'relacion': relacion[:-1], 'descripcion': 'Reposición de Caja Chica', 
                    'partner_id': self.employee_id.work_contact_id.id, 'amount_untaxed': total, 'amount_tax': 0.0, 'amount_total': total}
                req_lines.append((0, 0, lines))
        if self.destajo_ids:
            for rec in self.destajo_ids:
                if rec.amount_total != 0:
                    lines = {'category': 'Destajo', 'relacion': rec.id, 'descripcion': rec.type_des, 'partner_id': self.employee_id.work_contact_id.id, 
                        'amount_untaxed': rec.amount_total, 'amount_tax': 0.0, 'amount_total': rec.amount_total}
                    req_lines.append((0, 0, lines))
        if self.acarreo_ids:
            _logger.warning('Agregar Acarreos')
        if self.campamento_ids:
            _logger.warning('Agregar Campamentos')
        if self.maquinaria_ids:
            _logger.warning('Agregar Maquinaria')

        if self.nom_ids:
            total = 0
            relacion = ''
            for rec in self.nom_ids:
                if rec.salary != 0:
                    total += rec.salary
                    relacion = relacion + str(rec.id) + ','
            if relacion != '':
                lines = {'category': 'Nómina', 'relacion': relacion[:-1], 'descripcion': 'Nómina', 'partner_id': self.employee_id.work_contact_id.id, 
                    'amount_untaxed': total, 'amount_tax': 0.0, 'amount_total': total}
                req_lines.append((0, 0, lines))

        if self.line_ids:
            self.line_ids.unlink()

        _logger.warning(req_lines)


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('requisition.resident.name')
            employee = self.env['hr.employee'].search([('user_id','=',self.env.user.id)])
            if employee:
                vals['employee_id'] = employee.id
        return super().create(vals_list)


class requisitionResidentsLine(models.Model):
    _name = 'requisition.residents.line'
    _description = 'Resumen de la requisición'

    req_id = fields.Many2one('requisition.residents', readonly=True)
    category = fields.Char(string='Categoría', readonly=True)
    relacion = fields.Char(string='Relación')
    description = fields.Char(string='Descripción')
    partner_id = fields.Many2one('res.partner', string='Nombre', tracking=True)
    amount_untaxed = fields.Float(string='Importe sin IVA')
    amount_tax = fields.Float(string='Impuestos')
    amount_total = fields.Float(string='Total')

class requisitionDestajo(models.Model):
    _name = 'requisition.destajo'
    _description = 'Destajo'

    req_id = fields.Many2one('requisition.residents', readonly=True)
    type_des = fields.Char(string='Tipo de destajo')
    partner_id = fields.Many2one('res.partner', string='Nombre', tracking=True)
    fuerza = fields.Integer(string='No. de la cuadrilla del destajista')
    account_id = fields.Many2one('res.partner.bank', string='Cuenta Bancaria', tracking=True, ondelete='restrict', copy=False)
    croquis_id = fields.One2many('ir.attachment', 'res_id', string='Croquis')
    foto_ids = fields.Many2many(comodel_name='ir.attachment', string="Evidencia Fotográfica")
    cotizacion_id = fields.One2many('ir.attachment', 'res_id', string='Cotización o presupuesto')
    amount_total = fields.Float(string='Total', compute='_compute_amount', store=True, readonly=True)
    line_ids = fields.One2many('requisition.destajo.line', 'destajo_id')

    _sql_constraints = [('req_partner_uniq', 'unique (req_id, partner_id)', 'Solo debe de haber un destajo por destajista')]

    @api.depends('line_ids.amount')
    def _compute_amount(self):
        for req in self:
            total = 0.0
            for line in req.line_ids:
                total += line.amount
            req.amount_total = total
    

class requisitionDestajoLine(models.Model):
    _name = 'requisition.destajo.line'
    _description = 'Líneas de Destajo'

    destajo_id = fields.Many2one('requisition.destajo', readonly=True)
    fecha = fields.Date(string='Fecha')
    product_id = fields.Many2one(comodel_name='product.product', string='Concepto', change_default=True, ondelete='restrict', 
        domain="[('purchase_ok', '=', True)]")
    product_template_id = fields.Many2one(comodel_name='product.template', string='Product Template', compute='_compute_product_template_id',
        search='_search_product_template_id', domain=[('purchase_ok', '=', True)])
    product_uom_id = fields.Many2one(related='product_id.uom_id', depends=['product_id'], string='UdM')
    name = fields.Text(string='Descripcion')
    localizacion = fields.Char(string='Localización')
    ubicacion = fields.Char(string='Ubicación')
    price_unit = fields.Float(string='Precio unitario')
    largo = fields.Float(string='Largo')
    ancho = fields.Float(string='Ancho')
    alto = fields.Float(string='Alto')
    area = fields.Float(string='Área')
    volumen = fields.Float(string='Volumen')
    volumen_acum = fields.Float(string='Volumen acumulado')
    volumen_pres = fields.Float(string='Volumen presupuestado')
    volumen_ejec = fields.Float(string='Volumen por ejecutar')
    amount = fields.Float(string='Total')
    price = fields.Float(string='Precio catálogo')

    @api.onchange('fecha')
    def onchange_fecha(self):
        if self.fecha:
            if self.fecha > self.destajo_id.req_id.ffinal or self.fecha < self.destajo_id.req_id.finicio:
                raise ValidationError('La fecha capturada no esta dentro del periodo capturado')

    @api.onchange('largo', 'ancho', 'alto')
    def onchange_volumenes(self):
        if self.largo > 0 and self.ancho > 0:
            self.area = self.largo * self.ancho
            if self.alto > 0:
                self.volumen = self.area * self.alto
                self.amount = self.price_unit * self.volumen

    @api.depends('product_id')
    def _compute_product_template_id(self):
        for line in self:
            line.product_template_id = line.product_id.product_tmpl_id

    def _search_product_template_id(self, operator, value):
        return [('product_id.product_tmpl_id', operator, value)]


class requisitionAcarreos(models.Model):
    _name = 'requisition.acarreos'
    _description = 'Acarreos'

    req_id = fields.Many2one('requisition.residents', readonly=True)
    fecha = fields.Date(string='Fecha')
    partner_id = fields.Many2one('res.partner', string='Nombre', tracking=True) #, default=ICD transportes, S.A. DE C.V.)    
    product_id = fields.Many2one(comodel_name='product.product', string='Material', change_default=True, ondelete='restrict', 
        domain="[('purchase_ok', '=', True)]")
    product_template_id = fields.Many2one(comodel_name='product.template', string='Product Template', compute='_compute_product_template_id',
        search='_search_product_template_id', domain=[('purchase_ok', '=', True)])
    capacidad = fields.Char(string='Capacidad')
    origen = fields.Char(string='Origen')
    destino = fields.Char(string='Destino')
    km = fields.Float(string='Km recorrido')
    price = fields.Float(string='Precio Unitario')
    qty = fields.Float(string='Cantidad')
    amount = fields.Float(string='Importe')

    #amount = price * qty

    @api.depends('product_id')
    def _compute_product_template_id(self):
        for line in self:
            line.product_template_id = line.product_id.product_tmpl_id

    def _search_product_template_id(self, operator, value):
        return [('product_id.product_tmpl_id', operator, value)]

    @api.onchange('fecha')
    def onchange_fecha(self):
        if self.fecha:
            if self.fecha > self.req_id.ffinal or self.fecha < self.req_id.finicio:
                raise ValidationError('La fecha capturada no esta dentro del periodo capturado')

    @api.onchange('price', 'qty')
    def onchange_volumenes(self):
        if self.price > 0 and self.qty > 0:
            self.amount = self.price * self.qty


class requisitionCampamentos(models.Model):
    _name = 'requisition.campamentos'
    _description = 'Renta de campamentos'

    req_id = fields.Many2one('requisition.residents', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Beneficiario', tracking=True)    
    product_id = fields.Many2one(comodel_name='product.product', string='Material', change_default=True, ondelete='restrict', 
        domain="[('purchase_ok', '=', True)]")
    product_template_id = fields.Many2one(comodel_name='product.template', string='Product Template', compute='_compute_product_template_id',
        search='_search_product_template_id', domain=[('purchase_ok', '=', True)])
    finicio = fields.Date(string='Fecha Inicio')
    ffinal = fields.Date(string='Fecha Fin')
    ocupacion = fields.Char(string='Capacidad')
    price = fields.Float(string='Total Renta')
    periodo = fields.Char(string='Periodo')
    deposito = fields.Char(string='Depósito en garantía')

    @api.depends('product_id')
    def _compute_product_template_id(self):
        for line in self:
            line.product_template_id = line.product_id.product_tmpl_id

    def _search_product_template_id(self, operator, value):
        return [('product_id.product_tmpl_id', operator, value)]


class requisitionMaquinaria(models.Model):
    _name = 'requisition.maquinaria'
    _description = 'Maquinaria'

    req_id = fields.Many2one('requisition.residents', readonly=True)
    sequence = fields.Integer(string='Núm')
    partner_id = fields.Many2one('res.partner', string='Proveedor')
    maquinaria = fields.Char(string='Maquinaria/Equipo')
    no_serie = fields.Char(string='Num. de Serie')
    finicio = fields.Date(string='Fecha Ingreso')
    ffinal = fields.Date(string='Fecha Salida')
    days = fields.Float(string='Días trabajados')
    time_out = fields.Float(string='Tiempos muertos')
    total_days = fields.Float(string='Total días')
    rmountly = fields.Float(string='Monto Renta Mensual')
    amount = fields.Float(string='Importe')
    justification = fields.Char(string='Justificación del tiempo muerto')
    autoriza_id = fields.Many2one('hr.employee', string='Persona que autoriza renta y precio')
    line_ids = fields.One2many('requisition.maquinaria.line', 'maquinaria_id')
    horometro = fields.Float(string='Horometro Inicial')
    
    @api.onchange('days', 'time_out')
    def onchange_days(self):
        if self.days > 0 and self.time_out > 0:
            self.total_days = self.days - self.time_out

    @api.onchange('rmountly', 'time_out')
    def onchange_amount(self):
        if self.rmountly > 0 and self.total_days > 0:
            self.amount = (self.rmountly / 30) * self.total_days


class requisitionMaquinariaLine(models.Model):
    _name = 'requisition.maquinaria.line'
    _description = 'Desglose de uso de la maquinaria'

    maquinaria_id = fields.Many2one('requisition.maquinaria', readonly=True)
    fecha = fields.Date(string='Fecha')
    horometro = fields.Float(string='Horometro')
    hrs = fields.Float(string='Horas trabajadas')
    price = fields.Float(string='Precio litro')
    qty = fields.Float(string='Litros')
    amount = fields.Float(string='Importe')
    rendimiento = fields.Float(string='Rendimiento')
    vale = fields.Char(string='No. de valde de maquinaria')

    @api.depends('product_id')
    def _compute_product_template_id(self):
        for line in self:
            line.product_template_id = line.product_id.product_tmpl_id

    def _search_product_template_id(self, operator, value):
        return [('product_id.product_tmpl_id', operator, value)]

    @api.onchange('qty', 'price')
    def onchange_amount(self):
        if self.qty > 0 and self.price > 0:
            self.amount = self.qty * self.price


class requisitionCash(models.Model):
    _name = 'requisition.cash'
    _description = 'Caja Chica'

    req_id = fields.Many2one('requisition.residents', readonly=True)
    product_id = fields.Many2one(comodel_name='product.product', string='Elemento', change_default=True, ondelete='restrict', 
        domain="[('purchase_ok', '=', True)]")
    product_template_id = fields.Many2one(comodel_name='product.template', string='Product Template', compute='_compute_product_template_id',
        search='_search_product_template_id', domain=[('purchase_ok', '=', True)])
    fecha = fields.Date(string='Fecha')
    partner_id = fields.Many2one('res.partner', string='Proveedor')
    amount = fields.Float(string='Monto Gasto')
    categoria = fields.Many2one('product.tipo.insumo', string='Categoría')
    type_comp = fields.Selection(selection=[('tiq','Tiquet'), ('fact','Factura'), ('rem','Nota de remisión')],
        string='Tipo de comprobación', default='tiq', tracking=True)
    comp = fields.Boolean(string='Comprobación')
    observaciones = fields.Char(string='Observaciones')
    foto = fields.Binary(string='Foto', attachment=True)
    foto_name = fields.Char(string='Nombre de la foto del comprobante')

    @api.depends('product_id')
    def _compute_product_template_id(self):
        for line in self:
            line.product_template_id = line.product_id.product_tmpl_id

    def _search_product_template_id(self, operator, value):
        return [('product_id.product_tmpl_id', operator, value)]

    @api.onchange('fecha')
    def onchange_fecha(self):
        if self.fecha:
            if self.fecha > self.req_id.ffinal or self.fecha < self.req_id.finicio:
                raise ValidationError('La fecha capturada no esta dentro del periodo capturado')


class requisitionNomina(models.Model):
    _name = 'requisition.nomina'
    _description = 'Nómina'

    req_id = fields.Many2one('requisition.residents', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado')
    job_id = fields.Many2one('hr.job', string='Puesto')
    salary = fields.Float(string='Salario')
    observaciones = fields.Char(string='Observaciones')

    @api.depends('product_id')
    def _compute_product_template_id(self):
        for line in self:
            line.product_template_id = line.product_id.product_tmpl_id

    def _search_product_template_id(self, operator, value):
        return [('product_id.product_tmpl_id', operator, value)]

    @api.onchange('employee_id')
    def onchange_employee(self):
        if self.employee_id:
            self.job_id = self.employee_id.job_id