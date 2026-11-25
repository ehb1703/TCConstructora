# -*- coding: utf-8 -*-
from datetime import date
from markupsafe import Markup, escape
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from ..models.hr_employee import CURP, NSS

GRUPO = 'hr_destajistas.group_destajistas'


class HrDestajistaAlta(models.TransientModel):
    _name = 'hr.destajista.alta'
    _description = 'Alta rápida de destajista'

    # Solo contactos con la casilla "Es destajista" (Contactos) que aún no están ligados a un empleado o destajista
    contacto_id = fields.Many2one('res.partner', string='Contacto existente',
        domain=[('es_destajista', '=', True), ('is_company', '=', False), ('employee_ids', '=', False)],
        help='Contactos marcados como "Es destajista" en Contactos: elija el suyo para usar los mismos datos y cuenta bancaria.')
    nombre = fields.Char(string='Nombre(s)')
    apaterno = fields.Char(string='Apellido paterno')
    amaterno = fields.Char(string='Apellido materno')
    curp = fields.Char(string='CURP')
    nss = fields.Char(string='NSS')
    foto = fields.Image(string='Fotografía', max_width=1024, max_height=1024)
    cuenta_id = fields.Many2one('res.partner.bank', string='Cuenta bancaria del contacto', domain="[('partner_id', '=', contacto_id)]")
    banco_id = fields.Many2one('res.bank', string='Banco')
    numero_cuenta = fields.Char(string='Cuenta / CLABE')
    obra_id = fields.Many2one('project.project', string='Obra asignada', domain=[('active', '=', True)])
    obra_direccion = fields.Char(string='Dirección de la obra', compute='_compute_obra')
    residente_id = fields.Many2one('hr.employee', string='Residente responsable')
    horario_id = fields.Many2one('resource.calendar', string='Horario', help='Horario de trabajo que habilita el destajista (libre).')
    aviso = fields.Html(string='Avisos', compute='_compute_obra', sanitize=False)

    @api.depends('obra_id', 'residente_id')
    def _compute_obra(self):
        for wiz in self:
            obra = wiz.obra_id.sudo()
            wiz.obra_direccion = obra._direccion_obra() if obra else False
            avisos = []
            if obra and not obra._residente_obra():
                avisos.append(Markup(_('La obra <b>%s</b> no tiene residente capturado: elija aquí el residente responsable y pida que se registre en la obra.')) % obra.name)
            if obra and not wiz.obra_direccion:
                avisos.append(Markup(_('La obra <b>%s</b> no tiene dirección capturada: el destajista quedará sin dirección de obra hasta que se capture en la obra.')) % obra.name)
            wiz.aviso = Markup('<div class="alert alert-warning mb-0">%s</div>') % Markup('<br/>').join(avisos) if avisos else False

    @api.onchange('obra_id')
    def _onchange_obra(self):
        if self.obra_id:
            self.residente_id = self.obra_id._residente_obra() or self.residente_id

    @api.onchange('contacto_id')
    def _onchange_contacto(self):
        c = self.contacto_id.sudo()
        if c:
            self.nombre = c.nombre or self.nombre
            self.apaterno = c.apaterno or self.apaterno
            self.amaterno = c.amaterno or self.amaterno
            self.curp = c.curp or self.curp
            self.cuenta_id = c.bank_ids[:1]

    def _validar(self):
        self.ensure_one()
        if not self.env.user.has_group(GRUPO) and not self.env.user.has_group('hr.group_hr_user'):
            raise UserError(_('Solo el grupo Destajistas puede dar de alta destajistas.'))
        faltan = [n for n, v in ((_('Nombre(s)'), self.nombre or self.contacto_id), (_('Apellido paterno'), self.apaterno or self.contacto_id),
                                 (_('CURP'), self.curp), (_('NSS'), self.nss), (_('Fotografía'), self.foto),
                                 (_('Cuenta bancaria'), self.cuenta_id or self.numero_cuenta), (_('Obra asignada'), self.obra_id),
                                 (_('Residente responsable'), self.residente_id)) if not v]
        if faltan:
            raise UserError(_('Capture: %s.', ', '.join(faltan)))
        curp = self.curp.strip().upper()
        if not CURP.match(curp):
            raise UserError(_('La CURP %s no tiene el formato oficial (18 caracteres: 4 letras, fecha AAMMDD, sexo H/M, 5 letras y 2 de homoclave).', curp))
        if not NSS.match(self.nss.strip()):
            raise UserError(_('El NSS debe tener 11 dígitos.'))
        if self.numero_cuenta and not self.cuenta_id and not self.banco_id:
            raise UserError(_('Elija el banco de la cuenta.'))
        Empleado = self.env['hr.employee'].sudo().with_context(active_test=False)
        repetido = Empleado.search([('l10n_mx_curp', '=', curp), ('active', '=', True)], limit=1)
        if repetido:
            raise UserError(_('La CURP %(c)s ya está registrada en %(n)s (%(t)s).', c=curp, n=repetido.name,
                              t=dict(repetido._fields['tipo_personal'].selection)[repetido.tipo_personal]))
        if self.contacto_id and Empleado.search_count([('work_contact_id', '=', self.contacto_id.id), ('active', '=', True)]):
            raise UserError(_('El contacto %s ya está ligado a un empleado o destajista activo.', self.contacto_id.name))
        if self.contacto_id and hasattr(self.contacto_id, '_check_datos_fiscales_sat'):
            # Al darlo de alta se actualiza su contacto (CURP); si es proveedor o cliente, la regla fiscal de contactos (T0113) se revisa antes.
            # Sin T0113 instalada (main hoy) no hay regla fiscal que revisar.
            try:
                self.contacto_id.sudo()._check_datos_fiscales_sat()
            except ValidationError as e:
                raise UserError(_('Complete primero en Contactos los datos fiscales de %(c)s (es proveedor o cliente):\n%(m)s',
                                  c=self.contacto_id.name, m=e.args[0] if e.args else e))
        return curp

    def action_crear(self):
        curp = self._validar()
        env = self.sudo().env
        contacto = self.contacto_id.sudo()
        nombre_completo = ' '.join(p.strip().upper() for p in (self.nombre, self.apaterno, self.amaterno) if p and p.strip())
        if not contacto:
            contacto = env['res.partner'].create({'name': nombre_completo, 'nombre': (self.nombre or '').strip().upper(), 'es_destajista': True,
                                                   'apaterno': (self.apaterno or '').strip().upper(), 'amaterno': (self.amaterno or '').strip().upper()})
        elif not contacto.es_destajista:
            contacto.es_destajista = True
        cuenta = self.cuenta_id.sudo()
        if not cuenta:
            numero = self.numero_cuenta.strip()
            cuenta = env['res.partner.bank'].search([('partner_id', '=', contacto.id), ('acc_number', '=', numero)], limit=1) or \
                env['res.partner.bank'].create({'partner_id': contacto.id, 'acc_number': numero, 'bank_id': self.banco_id.id})
        try:
            with env.cr.savepoint():
                # hr_extra escribe CURP y RFC en el contacto al crear el empleado: se pasa el RFC que ya tiene para no borrarlo
                empleado = env['hr.employee'].create({
                    'name': contacto.name, 'legal_name': contacto.name, 'work_contact_id': contacto.id, 'tipo_personal': 'destajista',
                    'l10n_mx_curp': curp, 'l10n_mx_rfc': contacto.vat or False, 'ssnid': self.nss.strip(), 'image_1920': self.foto,
                    'bank_account_id': cuenta.id, 'destajo_residente_id': self.residente_id.id, 'resource_calendar_id': self.horario_id.id or False})
                env['hr.employee.obra'].create({'employee_id': empleado.id, 'project_id': self.obra_id.id, 'fecha_inicio': date.today()})
        except ValidationError as e:
            raise UserError(_('No se pudo dar de alta al destajista: %s', e.args[0] if e.args else e))
        return {'type': 'ir.actions.act_window', 'res_model': 'hr.employee', 'res_id': empleado.id, 'view_mode': 'form',
                'views': [(self.env.ref('hr_destajistas.view_destajista_form').id, 'form')], 'target': 'current'}
