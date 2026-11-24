# -*- coding: utf-8 -*-
import re
from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.hr_extra.models.hr_employee import _encargado_nomina_extra_domain

TIPOS_PERSONAL = [('empleado', 'Empleado'), ('destajista', 'Destajista')]
CURP = re.compile(r'^[A-Z][AEIOUX][A-Z]{2}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$')
NSS = re.compile(r'^\d{11}$')


class HrEmployeeDestajista(models.Model):
    _inherit = 'hr.employee'

    tipo_personal = fields.Selection(TIPOS_PERSONAL, string='Tipo de personal', default='empleado', required=True, index=True, tracking=True,
        help='Los destajistas están separados del padrón de empleados y no participan en la nómina.')
    destajo_residente_id = fields.Many2one('hr.employee', string='Residente responsable', tracking=True,
        help='Residente de la obra al que reporta el destajista.')
    destajo_obra_id = fields.Many2one('project.project', string='Obra asignada', compute='_compute_destajo_obra', store=True)
    destajo_obra_direccion = fields.Char(string='Dirección de la obra', compute='_compute_destajo_obra_direccion')
    # Datos del destajista sin el candado de RRHH de los campos nativos: el grupo Destajistas los captura y consulta solo en destajistas
    destajo_numero = fields.Char(string='Número de checador', compute='_compute_destajo_datos')
    destajo_curp = fields.Char(string='CURP', compute='_compute_destajo_datos', inverse='_inverse_destajo_curp')
    destajo_nss = fields.Char(string='NSS', compute='_compute_destajo_datos', inverse='_inverse_destajo_nss')
    destajo_cuenta_id = fields.Many2one('res.partner.bank', string='Cuenta bancaria', compute='_compute_destajo_datos', inverse='_inverse_destajo_cuenta')

    @api.depends('obra_ids.project_id', 'obra_ids.fecha_inicio', 'obra_ids.fecha_fin')
    def _compute_destajo_obra(self):
        # Misma vigencia que hr_extra (_compute_current_project) y mismo desempate que la checada (fecha_inicio DESC, id DESC):
        # si se cambia de obra el mismo día del alta, gana la asignación más reciente
        hoy = date.today()
        for emp in self:
            vigentes = emp.obra_ids.filtered(lambda o: o.project_id and o.project_id.active and o.fecha_inicio and o.fecha_inicio <= hoy
                                             and (not o.fecha_fin or hoy <= o.fecha_fin))
            buscar = vigentes or emp.obra_ids.filtered(lambda o: o.project_id and o.project_id.active)
            emp.destajo_obra_id = buscar.sorted(lambda o: (o.fecha_inicio, o.id), reverse=True)[:1].project_id if buscar else False

    @api.depends('destajo_obra_id')
    def _compute_destajo_obra_direccion(self):
        for emp in self:
            emp.destajo_obra_direccion = emp.destajo_obra_id.sudo()._direccion_obra() if emp.destajo_obra_id else False

    def _compute_destajo_datos(self):
        for emp, priv in zip(self, self.sudo()):
            emp.destajo_numero = priv.registration_number
            emp.destajo_curp = priv.l10n_mx_curp
            emp.destajo_nss = priv.ssnid
            emp.destajo_cuenta_id = priv.bank_account_id

    def _inverse_destajo_curp(self):
        self.check_access('write')
        for emp in self:
            emp.sudo().l10n_mx_curp = (emp.destajo_curp or '').strip().upper() or False

    def _inverse_destajo_nss(self):
        self.check_access('write')
        for emp in self:
            emp.sudo().ssnid = (emp.destajo_nss or '').strip() or False

    def _inverse_destajo_cuenta(self):
        self.check_access('write')
        for emp in self:
            emp.sudo().bank_account_id = emp.destajo_cuenta_id

    @api.model_create_multi
    def create(self, vals_list):
        destajistas = [v for v in vals_list if v.get('tipo_personal') == 'destajista']
        if destajistas and len(destajistas) != len(vals_list):
            return self.create(destajistas) | self.create([v for v in vals_list if v.get('tipo_personal') != 'destajista'])
        if destajistas:
            # hr_extra numera con 'numemployee'; con este contexto la secuencia entrega la serie D0001
            registros = super(HrEmployeeDestajista, self.with_context(alta_destajista=True)).create(vals_list)
            for emp in registros.sudo().filtered(lambda e: not e.registration_number):
                numero = self.env['ir.sequence'].sudo().next_by_code('hr.destajista')
                emp.write({'registration_number': numero, 'identification_id': numero})
            return registros.with_env(self.env)
        return super().create(vals_list)

    @api.constrains('tipo_personal', 'l10n_mx_curp', 'ssnid', 'image_1920', 'bank_account_id', 'destajo_residente_id')
    def _check_destajista(self):
        for emp in self.sudo().filtered(lambda e: e.tipo_personal == 'destajista'):
            faltan = [n for n, v in ((_('CURP'), emp.l10n_mx_curp), (_('NSS'), emp.ssnid), (_('Fotografía'), emp.image_1920),
                                     (_('Cuenta bancaria'), emp.bank_account_id), (_('Residente responsable'), emp.destajo_residente_id)) if not v]
            if faltan:
                raise ValidationError(_('Al destajista %(n)s le falta: %(f)s.', n=emp.name, f=', '.join(faltan)))
            if not CURP.match(emp.l10n_mx_curp or ''):
                raise ValidationError(_('La CURP %(c)s de %(n)s no tiene el formato oficial (18 caracteres).', c=emp.l10n_mx_curp, n=emp.name))
            if not NSS.match(emp.ssnid or ''):
                raise ValidationError(_('El NSS de %s debe tener 11 dígitos.', emp.name))
            if emp.contract_ids:
                raise ValidationError(_('%s tiene contrato: un destajista no lleva contrato ni participa en la nómina.', emp.name))

    @api.constrains('l10n_mx_curp', 'active')
    def _check_curp_unica(self):
        # Un destajista no repite la CURP de nadie activo; entre empleados directos no se agrega ninguna regla nueva
        for emp in self.sudo().filtered(lambda e: e.active and e.l10n_mx_curp):
            dominio = [('id', '!=', emp.id), ('l10n_mx_curp', '=', emp.l10n_mx_curp), ('active', '=', True)]
            if emp.tipo_personal != 'destajista':
                dominio.append(('tipo_personal', '=', 'destajista'))
            otro = self.sudo().search(dominio, limit=1)
            if otro:
                raise ValidationError(_('La CURP %(c)s ya está registrada en %(o)s (%(t)s).', c=emp.l10n_mx_curp, o=otro.name,
                                        t=dict(TIPOS_PERSONAL)[otro.tipo_personal]))

    def _search(self, domain, offset=0, limit=None, order=None):
        # hr_extra limita la búsqueda de empleados según el "Encargado de nómina" del usuario, incluso con sudo. Los destajistas no son
        # de nómina: siempre quedan visibles (los acotan sus reglas de acceso). Sin esto, un usuario de RRHH sin encargado asignado
        # no los ve y el alta falla al crear las hojas de horas de días festivos. Mismas excepciones que hr_extra; para los empleados
        # la restricción queda idéntica.
        crm = ('crm.lead', 'crm.junta.line', 'crm.propuesta.tecnica.revision', 'crm.propuesta.economica.revision')
        por_id = domain and len(domain) == 1 and isinstance(domain[0], (list, tuple)) and domain[0][0] == 'id' and domain[0][1] in ('=', 'in')
        if self.env.user.login == 'admin' or self._context.get('special_display') or por_id \
                or self._context.get('active_model') in crm or self._context.get('default_model') in crm:
            return super()._search(domain, offset=offset, limit=limit, order=order)
        extra = _encargado_nomina_extra_domain(self.env, 'self')
        if len(extra) != 1:
            return super()._search(domain, offset=offset, limit=limit, order=order)
        dominio = list(domain) + ['|', ('tipo_personal', '=', 'destajista')] + extra
        return super(HrEmployeeDestajista, self.with_context(special_display=True))._search(dominio, offset=offset, limit=limit, order=order)

    def get_employee_data_for_api(self):
        datos = super().get_employee_data_for_api()
        datos['personnel_type'] = self.tipo_personal
        if self.tipo_personal == 'destajista':
            datos['supervisor'] = self.destajo_residente_id.name or ''
        return datos


class ProjectProjectDestajista(models.Model):
    _inherit = 'project.project'

    def _direccion_obra(self):
        self.ensure_one()
        partes = [self.street, self.between_streets and _('entre %s', self.between_streets), self.col, self.zip and _('C.P. %s', self.zip),
                  self.city_id.municipio, self.state_id.name]
        return ', '.join(p for p in partes if p) or False

    def _residente_obra(self):
        self.ensure_one()
        return self.sudo().resident_ids.filtered('active')[:1].resident_id
