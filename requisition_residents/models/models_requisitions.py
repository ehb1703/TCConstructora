# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html_escape
from markupsafe import Markup
from datetime import date, datetime, timedelta, time
import json
import logging

_logger = logging.getLogger(__name__)


class requisitionResidents(models.Model):
    _name = 'requisition.residents'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _description = 'Requisiciones de Residentes de Obras'

    @api.depends('finicio')
    def _compute_domain_project(self):
        lista = []
        for record in self:
            if self.env.user.has_group('requisition_residents.group_requisition_admin'):
                projects = self.env['project.project'].search([('stage_id.name','!=','Cancelada')])
                for x in projects:
                    lista.append(x.id)
            else:
                employee = self.env['hr.employee'].search([('user_id','=',self.env.user.id)])
                residentes = self.env['project.residents'].search([('resident_id','=',employee.id)])
                for x in residentes:
                    lista.append(x.project_id.id)
            record.project_domain = json.dumps([('id', 'in', lista)])

    name = fields.Char(string='Nombre')
    finicio = fields.Date(string='Periodo Inicial')
    ffinal = fields.Date(string='Periodo Final')
    project_id = fields.Many2one('project.project', string='Obra')
    project_domain = fields.Char(readonly=True, store=False, compute=_compute_domain_project)
    employee_id = fields.Many2one('hr.employee', string='Responsable')
    company_id = fields.Many2one('res.company', string='Empresa', tracking=True)
    amount_untaxed = fields.Float(string='Importe sin IVA', compute='_compute_amount', store=True, readonly=True, tracking=True)
    amount_total = fields.Float(string='Importe con IVA', compute='_compute_amount', store=True, readonly=True)
    out_time = fields.Boolean(string='Fuera de tiempo', default=False)
    state = fields.Selection(selection=[('draft','Borrador'), ('send','Enviado'), ('aprobado','Aprobado'), ('req','Requisición')],
        string='Estatus', default='draft', tracking=True)
    line_ids = fields.One2many('requisition.residents.line', 'req_id', string='Resumen')
    destajo_ids = fields.One2many('requisition.destajo', 'req_id', string='Destajo')
    acarreo_ids = fields.One2many('requisition.acarreos', 'req_id', string='Acarreos')
    campamento_ids = fields.One2many('requisition.campamentos', 'req_id', string='Campamentos')
    maquinaria_ids = fields.One2many('requisition.maquinaria', 'req_id', string='Maquinaria')
    cash_ids = fields.One2many('requisition.cash', 'req_id', string='Caja Chica')
    nom_ids = fields.One2many('requisition.nomina', 'req_id', string='Nomina')
    rweekly_id = fields.Many2one('requisition.weekly', readonly=True)

    @api.depends('line_ids.amount_untaxed', 'line_ids.amount_total')
    def _compute_amount(self):
        for req in self:
            total_untaxed, total = 0.0, 0.0
            for line in req.line_ids:
                total_untaxed += line.amount_untaxed
                total += line.amount_total
            req.amount_untaxed = total_untaxed
            req.amount_total = total

    @api.onchange('finicio')
    def validar_fechas(self):
        if self.finicio:
            semana = self.env['requisition.residents'].search([('finicio','=',self.finicio), ('state','=','req')])
            if len(semana) >= 1:
                self.finicio = None
                raise ValidationError('La Requisición semanal ya fue generada para la fecha seleccionada.')
            if self.finicio.weekday() != 2:
                self.finicio = None
                raise ValidationError('La requisición debe iniciar en miércoles')

            self.ffinal = self.finicio + timedelta(days=6)

        if self.finicio and self.ffinal:
            dias = self.ffinal - self.finicio
            if dias.days > 6:
                raise ValidationError('El periodo seleccionado es mayor a una semana.')

    @api.onchange('project_id')
    @api.depends('project_id')
    def validar_obra(self):
        if self.finicio:
            existe = self.env['requisition.residents'].search([('finicio','=',self.finicio), ('project_id','!=',self.project_id.id), ('id','!=',self.id)])
            if existe:
                self.project_id = None
                raise ValidationError('Ya existe una requisición para la obra en el periodo seleccionado')

    def action_resumen(self):
        req_lines = []
        if self.nom_ids:
            total = 0
            fe = 0
            total_fiscal = 0
            ff = 0
            relacion = ''
            for rec in self.nom_ids:
                if rec.salary != 0:
                    if rec.employee_id.bank_account_id.type_pay == 'fiscal':
                        total_fiscal += rec.salary
                        ff += 1
                    else:
                        total += rec.salary
                        fe += 1
                    relacion = relacion + str(rec.id) + ','
            if relacion != '':
                lines = {'category': 'Nómina', 'relacion': relacion[:-1], 'description': 'Nómina', 'partner_id': self.employee_id.work_contact_id.id, 
                    'fuerza_untaxed': fe, 'amount_untaxed': total, 'fuerza_total': ff, 'amount_total': total_fiscal}
                req_lines.append((0, 0, lines))
        if self.cash_ids:
            total = 0
            total_fiscal = 0
            relacion = ''
            for rec in self.cash_ids:
                if rec.amount != 0:
                    if rec.type_comp == 'fact':
                        total_fiscal += rec.amount
                    else:
                        total += rec.amount
                    relacion = relacion + str(rec.id) + ','
            if relacion != '':
                lines = {'category': 'Caja Chica', 'relacion': relacion[:-1], 'description': 'Reposición de Caja Chica', 
                    'partner_id': self.employee_id.work_contact_id.id, 'amount_untaxed': total, 'amount_total': total_fiscal}
                req_lines.append((0, 0, lines))
        if self.campamento_ids:
            self.env.cr.execute('''SELECT partner_id, SUM(CASE WHEN ra.type_pay = 'FISCAL' THEN price ELSE 0 END) fiscal, 
                    SUM(CASE WHEN ra.type_pay = 'EFECTIVO' THEN price ELSE 0 END) efectivo
                FROM requisition_campamentos ra WHERE req_id = ''' + str(self.id) + ' GROUP BY 1')
            campamento = self.env.cr.dictfetchall()
            for rec in campamento:
                lines = {'category': 'Renta', 'description': 'Renta', 'partner_id': rec['partner_id'], 'amount_untaxed': rec['efectivo'], 
                    'amount_total': rec['fiscal']}
                req_lines.append((0, 0, lines))
        if self.maquinaria_ids:
            self.env.cr.execute('''SELECT partner_id, SUM(CASE WHEN ra.type_pay = 'FISCAL' THEN amount ELSE 0 END) fiscal, 
                    SUM(CASE WHEN ra.type_pay = 'EFECTIVO' THEN amount ELSE 0 END) efectivo
                FROM requisition_maquinaria ra WHERE req_id = ''' + str(self.id) + ' GROUP BY 1')
            maquinaria = self.env.cr.dictfetchall()
            for rec in maquinaria:
                lines = {'category': 'Renta', 'description': 'Maquinaria', 'partner_id': rec['partner_id'], 'amount_untaxed': rec['efectivo'], 
                    'amount_total': rec['fiscal']}
                req_lines.append((0, 0, lines))
        if self.acarreo_ids:
            self.env.cr.execute('''SELECT partner_id, SUM(CASE WHEN ra.type_pay = 'FISCAL' THEN amount ELSE 0 END) fiscal, 
                    SUM(CASE WHEN ra.type_pay = 'EFECTIVO' THEN amount ELSE 0 END) efectivo 
                FROM requisition_acarreos ra WHERE req_id = ''' + str(self.id) + ' GROUP BY 1')
            acarreo = self.env.cr.dictfetchall()
            for rec in acarreo:
                lines = {'category': 'Acarreos', 'description': 'Acarreos', 'partner_id': rec['partner_id'], 'amount_untaxed': rec['efectivo'], 
                    'amount_total': rec['fiscal']}
                req_lines.append((0, 0, lines))
        if self.destajo_ids:
            self.env.cr.execute('''SELECT pp.nombre, partner_id, SUM(CASE WHEN ra.type_pay = 'FISCAL' THEN amount_total ELSE 0 END) fiscal, 
                    SUM(CASE WHEN ra.type_pay = 'EFECTIVO' THEN amount_total ELSE 0 END) efectivo
                FROM requisition_destajo ra LEFT JOIN project_piecework pp ON ra.DESTAJO_ID = pp.ID WHERE ra.amount_total != 0 AND req_id = ''' + 
                str(self.id) + ' GROUP BY 1, 2')
            destajo = self.env.cr.dictfetchall()
            for rec in destajo:
                lines = {'category': 'Destajo', 'description': rec['nombre'], 'partner_id': rec['partner_id'], 'amount_untaxed': rec['efectivo'], 
                    'amount_total': rec['fiscal']}
                req_lines.append((0, 0, lines))

        if self.line_ids:
            self.line_ids.unlink()

        self.write({'line_ids': req_lines})


    def _get_emails(self, grupo=None):
        emails = set()
        group = self.env.ref(grupo, raise_if_not_found=False)
        if group:
            for user in group.users.filtered(lambda u: u.active and u.partner_id and u.partner_id.email):
                emails.add(user.partner_id.email.strip())

        for rec in self.project_id.type_id.technicalcat_id.email_ids:
            if rec.work_email:
                emails.add(rec.work_email.strip())
            elif rec.private_email:
                emails.add(rec.private_email.strip())
            elif rec.address_id.email:
                emails.add(rec.address_id.email.strip())
            else:
                raise UserError(('No existen correos configurados del empleado %s') % rec.name)

        return sorted(e for e in emails if '@' in e)


    def _post_html(self, title, old_stage=None, new_stage=None):
        parts = [f'<p>{html_escape(title)}</p>']
        if old_stage or new_stage:
            parts.append(
                f'<p>{html_escape(_('De'))} <b>{html_escape((old_stage and old_stage.name) or '-')}</b> '
                f'{html_escape(_('a'))} <b>{html_escape((new_stage and new_stage.name) or '-')}</b>.</p>')
        body = '<div>' + ''.join(parts) + '</div>'
        self.message_post(body=Markup(body), message_type='comment', subtype_xmlid='mail.mt_note')

    def action_send(self):
        existe = self.env['requisition.residents'].search([('finicio','=',self.finicio), ('project_id','!=',self.project_id.id), ('id','!=',self.id)])
        if existe:
            self.project_id = None
            raise ValidationError('Ya existe una requisición para la obra en el periodo seleccionado')
        if (self.amount_untaxed + self.amount_total) in (0, 0.0):
            raise ValidationError('No existe información en la requisición.')
        
        semana = self.env['requisition.residents'].search([('finicio','=',self.finicio), ('state','=','req')])
        if len(semana) >= 1:
            self.finicio = None
            raise ValidationError('La Requisición semanal ya fue generada para la fecha seleccionada.')
        if self.finicio.weekday() != 2:
            self.finicio = None
            raise ValidationError('La requisición debe iniciar en miércoles')

        self.action_resumen()
        # Generar archivo y adjuntarlo
        correos_list = self._get_emails('requisition_residents.group_requisition_admin')
        template = self.env.ref('requisition_residents.mail_tmpl_requisition_residents', raise_if_not_found=False)

        try:
            correos = ', '.join(correos_list)
            email_values = {'model': 'requisition_residents', 'email_to': correos}
            template.send_mail(self.id, force_send=True, email_values=email_values)
            self._post_html(_('Se envió correo a: ') + correos)
        except Exception:
            self._post_html(_('Error al enviar el correo'))

        fecha = datetime.combine(self.ffinal, time())
        normal = fecha + timedelta(days=1, hours=15)
        hoy = datetime.now()
        if hoy > normal:
            self.out_time = True

        self.state = 'send'

    def action_confirm(self):
        c = 0
        ccamp = len(self.campamento_ids.filtered(lambda u: not u.account_id))
        cmaq = len(self.maquinaria_ids.filtered(lambda u: not u.account_id))
        ccar = len(self.acarreo_ids.filtered(lambda u: not u.account_id))
        cdest = len(self.destajo_ids.filtered(lambda u: not u.account_id))
        c = ccamp + cmaq + ccar + cdest
        if c != 0:
            raise ValidationError('Hay información sin la cuenta bancaria a depositar, favor de revisar.')

        self.action_resumen()
        self.state = 'aprobado'

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
    _inherit = ['mail.thread', 'mail.activity.mixin']

    req_id = fields.Many2one('requisition.residents', readonly=True)
    category = fields.Char(string='Categoría', readonly=True)
    relacion = fields.Char(string='Relación')
    description = fields.Char(string='Descripción')
    partner_id = fields.Many2one('res.partner', string='Nombre', tracking=True)
    fuerza_untaxed = fields.Integer(string='Fuerza Efectivo')
    amount_untaxed = fields.Float(string='Importe sin IVA')
    fuerza_total = fields.Integer(string='Fuerza Fiscal')
    amount_total = fields.Float(string='Total')

class requisitionDestajo(models.Model):
    _name = 'requisition.destajo'
    _description = 'Destajo'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.depends('req_id')
    def _compute_domain_destajo(self):
        for record in self:
            if record.req_id:
                record.destajo_domain = json.dumps([('id', 'in', record.req_id.project_id.type_id.piecework_ids.ids)])

    req_id = fields.Many2one('requisition.residents', readonly=True)
    destajo_id = fields.Many2one('project.piecework', string='Tipo de destajo')
    destajo_domain = fields.Char(readonly=True, store=False, compute=_compute_domain_destajo)
    partner_id = fields.Many2one('res.partner', string='Nombre', tracking=True)
    fuerza = fields.Integer(string='No. de la cuadrilla del destajista')
    account_id = fields.Many2one('res.partner.bank', string='Cuenta Bancaria', tracking=True, ondelete='restrict', copy=False)
    croquis_id = fields.One2many('ir.attachment', 'res_id', string='Croquis')
    foto_ids = fields.Many2many(comodel_name='ir.attachment', string="Evidencia Fotográfica")
    cotizacion_id = fields.One2many('ir.attachment', 'res_id', string='Cotización o presupuesto')
    amount_total = fields.Float(string='Total', compute='_compute_amount', store=True, readonly=True)
    line_ids = fields.One2many('requisition.destajo.line', 'destajo_id')
    state = fields.Selection(related='req_id.state', string='Estatus')
    type_pay = fields.Char(string='Tipo de pago', compute='_compute_type_pay', store=True, readonly=True)

    _sql_constraints = [('req_partner_uniq', 'unique (req_id, partner_id)', 'Solo debe de haber un destajo por destajista')]

    @api.depends('line_ids.amount')
    def _compute_amount(self):
        for req in self:
            total = 0.0
            for line in req.line_ids:
                total += line.amount
            req.amount_total = total

    @api.depends('account_id')
    def _compute_type_pay(self):
        for req in self:
            if req.account_id:
                if req.account_id.type_pay == 'fiscal':
                    req.type_pay = 'FISCAL'
                else:
                    req.type_pay = 'EFECTIVO'
    

class requisitionDestajoLine(models.Model):
    _name = 'requisition.destajo.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
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
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Acarreos'

    req_id = fields.Many2one('requisition.residents', readonly=True)
    fecha = fields.Date(string='Fecha')
    partner_id = fields.Many2one('res.partner', string='Nombre', tracking=True, 
        default=lambda self: self.env['res.partner'].search([('name','=','ICD transportes, S.A. DE C.V.')]))
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
    account_id = fields.Many2one('res.partner.bank', string='Cuenta Bancaria', tracking=True, ondelete='restrict', copy=False)
    type_pay = fields.Char(string='Tipo de pago', compute='_compute_type_pay', store=True, readonly=True)
    state = fields.Selection(related='req_id.state', string='Estatus')

    @api.depends('product_id')
    def _compute_product_template_id(self):
        for line in self:
            line.product_template_id = line.product_id.product_tmpl_id

    def _search_product_template_id(self, operator, value):
        return [('product_id.product_tmpl_id', operator, value)]

    @api.depends('account_id')
    def _compute_type_pay(self):
        for req in self:
            if req.account_id:
                if req.account_id.type_pay == 'fiscal':
                    req.type_pay = 'FISCAL'
                else:
                    req.type_pay = 'EFECTIVO'

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
    _inherit = ['mail.thread', 'mail.activity.mixin']
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
    account_id = fields.Many2one('res.partner.bank', string='Cuenta Bancaria', tracking=True, ondelete='restrict', copy=False)
    type_pay = fields.Char(string='Tipo de pago', compute='_compute_type_pay', store=True, readonly=True)
    state = fields.Selection(related='req_id.state', string='Estatus')

    @api.depends('product_id')
    def _compute_product_template_id(self):
        for line in self:
            line.product_template_id = line.product_id.product_tmpl_id

    def _search_product_template_id(self, operator, value):
        return [('product_id.product_tmpl_id', operator, value)]

    @api.depends('account_id')
    def _compute_type_pay(self):
        for req in self:
            if req.account_id:
                if req.account_id.type_pay == 'fiscal':
                    req.type_pay = 'FISCAL'
                else:
                    req.type_pay = 'EFECTIVO'


class requisitionMaquinaria(models.Model):
    _name = 'requisition.maquinaria'
    _inherit = ['mail.thread', 'mail.activity.mixin']
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
    account_id = fields.Many2one('res.partner.bank', string='Cuenta Bancaria', tracking=True, ondelete='restrict', copy=False)
    type_pay = fields.Char(string='Tipo de pago', compute='_compute_type_pay', store=True, readonly=True)
    state = fields.Selection(related='req_id.state', string='Estatus')
    
    @api.onchange('days', 'time_out')
    def onchange_days(self):
        if self.days > 0 and self.time_out > 0:
            self.total_days = self.days - self.time_out

    @api.onchange('rmountly', 'time_out')
    def onchange_amount(self):
        if self.rmountly > 0 and self.total_days > 0:
            self.amount = (self.rmountly / 30) * self.total_days

    @api.depends('account_id')
    def _compute_type_pay(self):
        for req in self:
            if req.account_id:
                if req.account_id.type_pay == 'fiscal':
                    req.type_pay = 'FISCAL'
                else:
                    req.type_pay = 'EFECTIVO'


class requisitionMaquinariaLine(models.Model):
    _name = 'requisition.maquinaria.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
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

    @api.depends('account_id')
    def _compute_type_pay(self):
        for req in self:
            if req.account_id:
                if req.account_id.type_pay == 'fiscal':
                    req.type_pay = 'FISCAL'
                else:
                    req.type_pay = 'EFECTIVO'

    @api.onchange('qty', 'price')
    def onchange_amount(self):
        if self.qty > 0 and self.price > 0:
            self.amount = self.qty * self.price


class requisitionCash(models.Model):
    _name = 'requisition.cash'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Caja Chica'

    @api.depends('req_id')
    def _compute_domain_obra(self):
        for record in self:
            if record.req_id:
                residentes = self.env['project.residents'].search([('resident_id','=',record.req_id.employee_id.id)])
                lista = []
                for x in residentes:
                    lista.append(x.project_id.id)
                record.project_domain = json.dumps([('id', 'in', lista)])

    req_id = fields.Many2one('requisition.residents', readonly=True)
    project_id = fields.Many2one('project.project', string='Obra')
    project_domain = fields.Char(readonly=True, store=False, compute=_compute_domain_obra)
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
    reference = fields.Char(string='Referencia')
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

    # Falta agregar la validación de que la línea no exista en otra requisición, una vez que se tengan ejemplos de captura


class requisitionNomina(models.Model):
    _name = 'requisition.nomina'
    _inherit = ['mail.thread', 'mail.activity.mixin']
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


class requisitionWeekly(models.Model):
    _name = 'requisition.weekly'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Requisiciones Semanales'

    name = fields.Char(string='Nombre')
    finicio = fields.Date(string='Periodo Inicial')
    amount_total = fields.Float(string='Total Adeudo', compute='_compute_amount', store=True, readonly=True)
    amount_pago = fields.Float(string='Total Pago', compute='_compute_amount', store=True, readonly=True)
    line_ids = fields.One2many('requisition.weekly.line', 'weekly_id', string='Resumen')
    reqres_ids = fields.One2many('requisition.residents', 'rweekly_id', string='Requisición Residente')
    state = fields.Selection(selection=[('draft','Borrador'), ('rev','Revisión'), ('apr','Aprobado'), ('done', 'Pagado')],
        string='Estatus', default='draft', tracking=True)

    @api.depends('line_ids.adeudo', 'line_ids.importe')
    def _compute_amount(self):
        for req in self:
            total, pago = 0.0, 0.0
            for line in req.line_ids:
                total += line.adeudo
                if line.aprobado:
                    pago += line.adeudo
                else:
                    pago += line.importe
            req.amount_total = total
            req.amount_pago = pago

    def action_send_rev(self):
        self.write({'state': 'rev'})

    def action_confirm(self):
        if not self.env.user.has_group('requisition_residents.group_requisition_authorize'):
            raise UserError('El usuario no tiene las facultades para realizar esta acción')

        for rec in self.line_ids:
            if not rec.aprobado and rec.importe == 0.0:
                raise ValidationError('El registro del concepto %s no esta aprobado, favor de revisar'% rec.concepto)
            if not rec.aprobado and rec.importe != 0.0 and rec.importe > rec.adeudo:
                raise ValidationError('El registro del concepto %s tiene un importe mayor al aprobado, favor de revisar'% rec.concepto)

        self.write({'state': 'apr'})

    def action_pay(self):
        self.env.cr.execute('''SELECT accountbank_id, balance, now()::date fecha, STRING_AGG(rwl.concepto, ',') concepto, 
                SUM(CASE WHEN aprobado IS True THEN adeudo ELSE importe END) importe
            FROM requisition_weekly_line rwl JOIN requisition_bank_account rba ON rwl.accountbank_id = rba.id 
            WHERE rwl.weekly_id = ''' + str(self.id) + ' GROUP BY 1, 2, 3')
        saldo = self.env.cr.dictfetchall()
        for rec in saldo:
            if rec['importe'] > rec['balance']:
                cuenta = self.env['requisition.bank.account'].search([('id','=',rec['accountbank_id'])])
                raise UserError('El saldo de %s la cuenta %s no es suficiente para realizar este pago' % (rec['balance'], cuenta.res_partner_bank.acc_number))

        for rec in saldo:
            adeudo_lines = []
            cuenta = self.env['requisition.bank.account'].search([('id','=',rec['accountbank_id'])])
            cta_line = self.env['requisition.bank.movements'].create({'fecha': rec['fecha'], 'debit': 0.0, 'credit': rec['importe'], 'origen': self.name, 
                'concepto': rec['concepto'], 'reqw_id': self.id, 'mov_id': cuenta.id})

            for ad in self.line_ids.filtered(lambda u: u.accountbank_id.id == cuenta.id):
                if ad.aprobado:
                    importe = ad.adeudo
                else:
                    importe = ad.importe

                ade_line = self.env['requisition.debt.line'].create({'fecha': rec['fecha'], 'project_id': ad.project_id.id, 'debit': 0.0, 'credit': importe, 
                    'concepto': ad.concepto, 'origen': self.name, 'reqw_id': self.id, 'movcta_id': cta_line.id, 'req_id': ad.debt_id.req_id.id, 
                    'reqres_id': ad.debt_id.id, 'type_pay': ad.type_pay})
            self.write({'state': 'done'})


class requisitionWeeklyLine(models.Model):
    _name = 'requisition.weekly.line'
    _description = 'Movimientos'
    _order = 'company_id asc, project_id asc, id asc'

    weekly_id = fields.Many2one('requisition.weekly', readonly=True)
    company_id = fields.Many2one('res.company', string='Empresa', tracking=True)
    project_id = fields.Many2one('project.project', string='Obra')
    concepto = fields.Char(string='Concepto')
    partner_id = fields.Many2one('res.partner', string='Proveedor')
    supplier_id = fields.Many2one('requisition.debt', string='Edo. cuenta')
    origen = fields.Char(string='Origen')
    fuerza = fields.Integer(string='Fuerza de trabajo')
    type_pay = fields.Char(string='Forma de pago')
    adeudo = fields.Float(string='Adeudo')
    aprobado = fields.Boolean(string='Adeudo aprobado', default=False)
    importe = fields.Float(string='Abono', default='0.0')
    accountbank_id = fields.Many2one('requisition.bank.account', string='Cuenta bancaria', domain="[('obsolete', '=', False)]")
    debt_id = fields.Many2one('requisition.debt.line', string='Linea de adeudo')
    state = fields.Selection(related='weekly_id.state', string='Estatus')
