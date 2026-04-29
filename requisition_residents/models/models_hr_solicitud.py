# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.models import Command
from markupsafe import Markup
from odoo.tools import html_escape
import json
import logging

_logger = logging.getLogger(__name__)

class RequisitionHrSolicitud(models.Model):
    _name = 'requisition.hr.solicitud'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'tipo_tramite'
    _description = 'Solicitudes de Alta/Baja de Personal'
    _order = 'fecha_aplicacion desc, id desc'

    @api.depends('tipo_tramite')
    def _compute_domain_employee(self):
        lista = []
        for record in self:
            employee = self.env['hr.employee'].sudo().search([('state','not in',['baja','pensionado'])])
            if self.tipo_tramite == 'rehabilitacion':
                employee = self.env['hr.employee'].sudo().search([('state','=','baja')])

            for x in employee:
                if x.name != 'ADMINISTRADOR':
                    contrato = x.sudo().contract_id
                    if contrato.schedule_pay == 'weekly':
                        lista.append(x.id)
                    elif not contrato:
                        lista.append(x.id)
            record.employee_domain = json.dumps([('id', 'in', lista)])

    tipo_tramite = fields.Selection(selection=[('alta','Alta'), ('rehabilitacion','Rehabilitación'), ('actualizacion','Actualización de datos'), 
        ('baja','Baja')], 
        string='Tipo de Trámite', required=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado')
    employee_domain = fields.Char(readonly=True, store=False, compute=_compute_domain_employee)
    nombre = fields.Char(string='Nombre(s)')
    apellido_paterno = fields.Char(string='Apellido paterno')
    apellido_materno = fields.Char(string='Apellido materno')
    calle = fields.Char(string='Calle')
    colonia = fields.Char(string='Colonia')
    municipio_id = fields.Many2one('res.municipalities', string='Municipio', tracking=True)
    estado_id = fields.Many2one('res.country.state', tracking=True, domain="[('country_id.code','=','MX')]")
    codigo_postal = fields.Char(string='Código postal')
    fecha_aplicacion = fields.Date(string='Fecha de aplicación')
    nss = fields.Char(string='NSS')
    rfc = fields.Char(string='RFC')
    curp = fields.Char(string='CURP')
    genero = fields.Selection(selection=[('male','Masculino'), ('female','Femenino'), ('other','Otros')], string='Género')
    fecha_nacimiento = fields.Date(string='Fecha de nacimiento')
    ciudad_nacimiento = fields.Char(string='Ciudad de nacimiento')
    res_bank = fields.Many2one('res.bank', string='Banco')
    notarjeta = fields.Char(string='Número de tarjeta')
    clabe = fields.Char(string='Clabe interbancaria')
    nocuenta = fields.Char(string='Número de cuenta')
    type_pay = fields.Selection(selection=[('estrategia','Estrategia'), ('fiscal','Fiscal')],
        string='Tipo', default='estrategia')
    project_id = fields.Many2one('project.project', string='Nombre de la obra')
    company_id = fields.Many2one('res.company', string='Empresa empleadora')
    resource_calendar_id = fields.Many2one('resource.calendar', 'Horario de Trabajo', domain="['|', ('company_id','=',False), ('company_id','=',1)]")
    job_id = fields.Many2one('hr.job', string='Puesto')
    salary = fields.Float(string='Salario por hora')
    departure_reason_id = fields.Many2one('hr.departure.reason', string='Motivo de la salida')
    observaciones = fields.Char(string='Observaciones')
    state = fields.Selection(selection=[('draft','Borrador'), ('send','Enviado'), ('aprobado','Aprobado')],
        string='Estatus', default='draft', tracking=True)
    doc_acta_nacimiento = fields.Binary(string='Acta de nacimiento', attachment=True)
    doc_acta_nacimiento_name = fields.Char(string='Acta de nacimiento nombre')
    doc_curp = fields.Binary(string='CURP', attachment=True)
    doc_curp_name = fields.Char(string='CURP nombre')
    doc_nss = fields.Binary(string='NSS', attachment=True)
    doc_nss_name = fields.Char(string='NSS nombre')
    doc_ine = fields.Binary(string='Identificación oficial (INE)', attachment=True)
    doc_ine_name = fields.Char(string='INE nombre')
    doc_comprobante_domicilio = fields.Binary(string='Comprobante de domicilio', attachment=True)
    doc_comprobante_domicilio_name = fields.Char(string='Comprobante de domicilio nombre')
    salary_semanal = fields.Float(string='Sueldo semanal', compute='_compute_baja_info', store=False)
    antiguedad = fields.Char(string='Antigüedad', compute='_compute_baja_info', store=False)
    dias_vacaciones = fields.Integer(string='Días de vacaciones disfrutadas', compute='_compute_baja_info', store=False)
    mostrar_vacaciones = fields.Boolean(string='Mostrar vacaciones', compute='_compute_baja_info', store=False)
    fecha_ingreso = fields.Date(string='Fecha de ingreso', compute='_compute_fecha_ingreso', store=False)
    motivo_rechazo = fields.Text(string='Motivo de rechazo', tracking=True)

    @api.depends('employee_id', 'tipo_tramite')
    def _compute_baja_info(self):
        for rec in self:
            if rec.tipo_tramite == 'baja' and rec.employee_id:
                contrato = rec.employee_id.sudo().contract_id
                # Contratos por hora usan hourly_wage * horas semanales
                if contrato:
                    if contrato.wage_type == 'hourly':
                        calendar = contrato.resource_calendar_id
                        horas_dia = calendar.hours_per_day if calendar else 8
                        rec.salary_semanal = contrato.hourly_wage * horas_dia * 6
                    else:
                        rec.salary_semanal = contrato.wage
                else:
                    rec.salary_semanal = 0.0

                if contrato and contrato.date_start:
                    from dateutil.relativedelta import relativedelta
                    from datetime import date
                    fecha_ref = rec.fecha_aplicacion or date.today()
                    delta = relativedelta(fecha_ref, contrato.date_start)
                    años = delta.years
                    meses = delta.months
                    rec.antiguedad = f'{años} año(s) {meses} mes(es)'
                    rec.mostrar_vacaciones = años >= 1
                    if rec.mostrar_vacaciones:
                        vacaciones_tomadas = rec.env['hr.leave'].sudo().search([
                            ('employee_id', '=', rec.employee_id.id),
                            ('state', '=', 'validate'),
                            ('holiday_status_id.work_time_rate', '!=', 100),
                        ])
                        rec.dias_vacaciones = int(sum(vacaciones_tomadas.mapped('number_of_days')))
                    else:
                        rec.dias_vacaciones = 0
                else:
                    rec.antiguedad = ''
                    rec.mostrar_vacaciones = False
                    rec.dias_vacaciones = 0
            else:
                rec.salary_semanal = 0.0
                rec.antiguedad = ''
                rec.mostrar_vacaciones = False
                rec.dias_vacaciones = 0

    @api.depends('employee_id', 'tipo_tramite')
    def _compute_fecha_ingreso(self):
        for rec in self:
            if rec.employee_id and rec.tipo_tramite in ['baja', 'actualizacion']:
                contrato = rec.employee_id.sudo().contract_id
                rec.fecha_ingreso = contrato.date_start if contrato else False
            else:
                rec.fecha_ingreso = False

    def action_rechazar(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Rechazar solicitud',
            'res_model': 'requisition.rechazar.solicitud',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_solicitud_id': self.id},}

    @api.constrains('nss')
    def _check_nss(self):
        for rec in self:
            if rec.nss and (' ' in rec.nss or '-' in rec.nss):
                raise ValidationError('El NSS no puede contener guiones ni espacios.')

    @api.constrains('curp')
    def _check_curp(self):
        for rec in self:
            if rec.curp:
                if ' ' in rec.curp or '-' in rec.curp:
                    raise ValidationError('El CURP no puede contener guiones ni espacios.')
                if len(rec.curp) != 18:
                    raise ValidationError('El CURP debe tener exactamente 18 caracteres.')

    @api.depends('tipo_tramite', 'employee_id', 'nombre', 'apellido_paterno', 'apellido_materno')
    def _compute_display_name(self):
        for rec in self:
            if rec.tipo_tramite:
                if rec.employee_id:
                    rec.display_name = f'{rec.tipo_tramite.upper()} - {rec.employee_id.name}'
                elif not rec.employee_id:
                    rec.display_name = f'{rec.tipo_tramite.upper()} - {rec.nombre} {rec.apellido_paterno} {rec.apellido_materno}'
            else:
                rec.display_name = f''

    @api.onchange('employee_id')
    def onchange_employee(self):
        if self.employee_id:
            self.apellido_paterno = self.employee_id.work_contact_id.apaterno
            self.apellido_materno = self.employee_id.work_contact_id.amaterno
            self.nombre = self.employee_id.work_contact_id.nombre
            self.nss = self.employee_id.ssnid
            self.rfc = self.employee_id.l10n_mx_rfc
            self.curp = self.employee_id.l10n_mx_curp
            self.genero = self.employee_id.gender
            self.fecha_nacimiento = self.employee_id.birthday
            self.ciudad_nacimiento = self.employee_id.place_of_birth
            self.calle = self.employee_id.work_contact_id.street
            self.colonia = self.employee_id.work_contact_id.street2
            self.estado_id = self.employee_id.work_contact_id.state_id
            self.codigo_postal = self.employee_id.work_contact_id.zip
            self.res_bank = self.employee_id.bank_account_id.bank_id
            self.notarjeta = self.employee_id.bank_account_id.no_tarjeta
            self.clabe = self.employee_id.bank_account_id.l10n_mx_edi_clabe
            self.nocuenta = self.employee_id.bank_account_id.acc_number
            if self.tipo_tramite == 'baja':
                self.job_id = self.employee_id.job_id

    def _post_html(self, title, old_stage=None, new_stage=None):
        parts = [f'<p>{html_escape(title)}</p>']
        if old_stage or new_stage:
            parts.append(
                f'<p>{html_escape(_('De'))} <b>{html_escape((old_stage and old_stage.name) or '-')}</b> '
                f'{html_escape(_('a'))} <b>{html_escape((new_stage and new_stage.name) or '-')}</b>.</p>')
        body = '<div>' + ''.join(parts) + '</div>'
        self.message_post(body=Markup(body), message_type='comment', subtype_xmlid='mail.mt_note')

    def _check_documento(self, field_name):
        self.ensure_one()
        if self[field_name]:
            return True
        adjunto = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('res_field', '=', field_name),
        ], limit=1)
        return bool(adjunto)

    def validation_inf(self):
        if self.tipo_tramite == 'alta':
            name = self.nombre + ' ' + self.apellido_paterno + ' ' + self.apellido_materno
            nombre = self.env['hr.employee'].search([('name','=',name)])
            if len(nombre) >= 1:
                raise ValidationError('Ya existe empleado con la información capturada.')

            if not self.nocuenta and not self.clabe and not self.notarjeta:
                raise ValidationError('Se debe de capturar al menos un dato de la información bancaria.')

            if not self.calle or not self.colonia or not self.codigo_postal or not self.estado_id or not self.municipio_id:
                raise ValidationError('Los campos de dirección son obligatorios para el trámite de Alta.')

            if not self._check_documento('doc_acta_nacimiento'):
                raise ValidationError('El documento Acta de nacimiento es requerido para el trámite de Alta.')
            if not self._check_documento('doc_curp'):
                raise ValidationError('El documento CURP es requerido para el trámite de Alta.')
            if not self._check_documento('doc_nss'):
                raise ValidationError('El documento NSS es requerido para el trámite de Alta.')
            if not self._check_documento('doc_ine'):
                raise ValidationError('La Identificación oficial (INE) es requerida para el trámite de Alta.')
            if not self._check_documento('doc_comprobante_domicilio'):
                raise ValidationError('El Comprobante de domicilio es requerido para el trámite de Alta.')

        if self.tipo_tramite == 'rehabilitacion':
            if not self.calle or not self.colonia or not self.codigo_postal or not self.estado_id or not self.municipio_id:
                raise ValidationError('Los campos de dirección son obligatorios para el trámite de Rehabilitación.')

            if not self._check_documento('doc_ine'):
                raise ValidationError('La Identificación oficial (INE) es requerida para el trámite de Rehabilitación.')
            if not self._check_documento('doc_comprobante_domicilio'):
                raise ValidationError('El Comprobante de domicilio es requerido para el trámite de Rehabilitación.')

        if self.tipo_tramite == 'baja':
            current_contract = self.employee_id.sudo().contract_id
            if current_contract and current_contract.date_start > self.fecha_aplicacion:
                raise ValidationError(_('La fecha de salida no puede ser anterior a la fecha de inicio del contrato actual.'))

        if self.tipo_tramite == 'rehabilitacion':
            current_contract = self.employee_id.sudo().contract_id
            if current_contract and current_contract.date_end > self.fecha_aplicacion:
                raise ValidationError(_('La fecha de aplicación debe ser mayor a la fecha de salida del ultimo contrato.'))


    def action_send(self):
        self.validation_inf()
        emails = set()
        nombre = self.env['hr.employee'].search([('encargado_nomina','in',['ambas','semanal'])])
        for rec in nombre:
            if rec.work_email:
                emails.add(rec.work_email.strip())
            elif rec.private_email:
                emails.add(rec.private_email.strip())
            elif rec.address_id.email:
                emails.add(rec.address_id.email.strip())
            else:
                raise ValidationError(('No existen correos configurados del empleado %s') % rec.name)
        
        correos_list = sorted(e for e in emails if '@' in e)
        template = self.env.ref('requisition_residents.mail_tmpl_requisition_rh_solicitud', raise_if_not_found=False)
        try:
            correos = ', '.join(correos_list)
            email_values = {'model': 'requisition_rh_solicitud', 'email_to': correos}
            template.send_mail(self.id, force_send=True, email_values=email_values)
            self._post_html(_('Se envió correo a: ') + correos)
        except Exception:
            self._post_html(_('Error al enviar el correo'))

        self.state = 'send'


    def action_confirm(self):
        self.validation_inf()
        depto = self.env['hr.department'].search([('name','=','PERSONAL DE OPERACIÓN')])
        est = self.env['hr.payroll.structure.type'].search([('name','=','Mexico: Employee')])
        type = self.env['hr.contract.type'].search([('name','=','Obra determinada')])
        name = self.nombre + ' ' + self.apellido_paterno + ' ' + self.apellido_materno

        if self.tipo_tramite == 'alta':
            nombre = self.env['res.partner'].search([('name','=',name)])
            if len(nombre) >= 1:
                contact = nombre
            else:
                contact = self.env['res.partner'].create({'apaterno':self.apellido_paterno, 'amaterno':self.apellido_materno, 'nombre':self.nombre, 
                    'street':self.calle, 'street2':self.colonia, 'zip':self.codigo_postal, 'city':self.municipio_id.municipio, 'state_id':self.estado_id.id, 
                    'country_id':self.estado_id.country_id.id, 'vat':self.rfc, 'curp':self.curp, 'is_company':False, 'name':name, 'is_employee':True})

            self.env.cr.execute('SELECT * FROM res_partner_bank rpb WHERE rpb.partner_id = ' + str(contact.id) + ' AND rpb.bank_id = ' + 
                str(self.res_bank.id) + " AND (rpb.acc_number = '" + str(self.nocuenta) + "' OR rpb.l10n_mx_edi_clabe = '" + str(self.clabe) + 
                "' OR rpb.no_tarjeta = '" + str(self.notarjeta) + "')")
            tarjeta = self.env.cr.dictfetchall()
            if not tarjeta:
                if self.nocuenta:
                    acc_number = self.nocuenta
                else:
                    if self.clabe:
                        acc_number = self.clabe
                    else:
                        acc_number = self.notarjeta

                cuenta = self.env['res.partner.bank'].create({'acc_number':acc_number, 'bank_id':self.res_bank.id, 'no_tarjeta':self.notarjeta, 
                    'partner_id':contact.id, 'type_pay':self.type_pay, 'allow_out_payment':True})
            else:
                cuenta = self.env['res.partner.bank'].search([('id','=',tarjeta[0]['id'])])

            employee = self.env['hr.employee'].create({'work_contact_id':contact.id, 'name':contact.name, 'legal_name':contact.name, 
                'empresa_empleadora':self.company_id.id, 'job_id':self.job_id.id, 'department_id':depto.id, 'resource_calendar_id':self.resource_calendar_id.id,
                'private_street':self.calle, 'private_street2':self.colonia, 'private_zip':self.codigo_postal, 'private_city':self.municipio_id.municipio, 
                'private_state_id':self.estado_id.id, 'private_country_id':self.estado_id.country_id.id, 'l10n_mx_rfc':self.rfc, 'l10n_mx_curp':self.curp, 
                'gender':self.genero, 'ssnid':self.nss, 'birthday':self.fecha_nacimiento, 'place_of_birth':self.ciudad_nacimiento, 'state':'activo', 
                'active':True, 'bank_account_id':cuenta.id})
            obra = self.env['hr.employee.obra'].create({'employee_id':employee.id, 'project_id':self.project_id.id, 'fecha_inicio':self.fecha_aplicacion,
                'hourly_wage':self.salary})
            contrato = self.env['hr.contract'].create({'name':employee.registration_number + ' - ' + name, 'employee_id':employee.id, 
                'date_start':self.fecha_aplicacion, 'resource_calendar_id':self.resource_calendar_id.id, 'work_entry_source':'attendance', 
                'structure_type_id':est.id, 'job_id':self.job_id.id, 'department_id':depto.id, 'contract_type_id':type.id, 'project_id':self.project_id.id,
                'wage_type':'hourly', 'schedule_pay':'weekly', 'state':'open', 'wage':0})

        if self.tipo_tramite == 'baja':
            self.employee_id.write({'state':'baja', 'departure_reason_id':self.departure_reason_id, 'departure_description':self.observaciones, 
                'departure_date':self.fecha_aplicacion})

            current_contract = self.employee_id.sudo().contract_id
            self.employee_id.sudo().contract_ids.filtered(lambda c: c.state == 'draft').write({'state': 'cancel'})
            if current_contract and current_contract.state in ['open', 'draft']:
                current_contract.sudo().write({'date_end': self.fecha_aplicacion})
            if current_contract and current_contract.state == 'open':
                current_contract.sudo().write({'state': 'close'})
            
            self.employee_id.update({'equipment_ids': [Command.unlink(equipment.id) for equipment in self.employee_id.equipment_ids]})
            for rec in self.employee_id.obra_ids.filtered(lambda c: not c.fecha_fin):
                rec.update({'fecha_fin': self.fecha_aplicacion})
                if not rec.fecha_inicio:
                    rec.update({'fecha_inicio': self.fecha_aplicacion})

            self.employee_id.work_contact_id.is_employee = False

        if self.tipo_tramite == 'rehabilitacion':
            self.employee_id.write({'state':'activo', 'empresa_empleadora':self.company_id, 'job_id':self.job_id.id, 'department_id':depto.id, 
                'resource_calendar_id':self.resource_calendar_id.id})
            obra = self.env['hr.employee.obra'].create({'employee_id':self.employee_id.id, 'project_id':self.project_id.id, 'fecha_inicio':self.fecha_aplicacion,
                'hourly_wage':self.salary})
            contrato = self.env['hr.contract'].create({'name':self.employee_id.registration_number + ' - ' + name, 'employee_id':self.employee_id.id, 
                'date_start':self.fecha_aplicacion, 'resource_calendar_id':self.resource_calendar_id.id, 'work_entry_source':'attendance', 
                'structure_type_id':est.id, 'job_id':self.job_id.id, 'department_id':depto.id, 'contract_type_id':type.id, 'project_id':self.project_id.id,
                'wage_type':'hourly', 'schedule_pay':'weekly', 'state':'open', 'wage':0})
            self.employee_id.work_contact_id.is_employee = True

        if self.tipo_tramite == 'actualizacion':
            emp = {}
            con = {}
            if self.fecha_nacimiento != self.employee_id.birthday:
                emp['birthday'] =  self.fecha_nacimiento
            if self.ciudad_nacimiento != self.employee_id.place_of_birth:
                emp['place_of_birth'] =  self.ciudad_nacimiento
            if self.genero != self.employee_id.gender:
                emp['gender'] =  self.genero
            if self.rfc != self.employee_id.l10n_mx_rfc:
                emp['l10n_mx_rfc'] = self.rfc
            if self.curp != self.employee_id.l10n_mx_curp:
                emp['l10n_mx_curp'] = self.curp
            if self.nss != self.employee_id.ssnid:
                emp['ssnid'] = self.nss
            if self.calle != self.employee_id.private_street:
                emp['private_street'] = self.calle
                con['street'] = self.calle
            if self.colonia != self.employee_id.private_street2:
                emp['private_street2'] = self.colonia
                con['street2'] = self.colonia
            if self.codigo_postal != self.employee_id.private_zip:
                emp['private_zip'] = self.codigo_postal
                con['zip'] = self.codigo_postal
            if self.estado_id.country_id.id != self.employee_id.private_country_id.id:
                emp['private_country_id'] = self.estado_id.country_id.id
                con['country_id'] = self.estado_id.country_id.id
            if self.municipio_id:
                if self.municipio_id.municipio != self.employee_id.private_city:
                    emp['private_city'] = self.municipio_id.municipio
                    con['city'] = self.municipio_id.municipio

            if emp:
                self.employee_id.write(emp)
            if con:
                self.employee_id.work_contact_id.write(con)

        self.state = 'aprobado'
