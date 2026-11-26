# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .seguridad import NIVEL_2, NIVEL_3, exigir_nivel


class GestionObraContrato(models.Model):
    _name = 'gestion.obra.contrato'
    _description = 'Contrato y Subcontrato de Obra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Folio de Contrato', required=True, readonly=True, copy=False, default=lambda self: _('Nuevo'))
    partner_id = fields.Many2one('res.partner', string='Subcontratista', required=True, tracking=True,
        domain="[('tipo_contratista', '!=', False)]", help='Solo se pueden elegir contactos con el expediente digital completo.')
    project_id = fields.Many2one('project.project', string='Obra / Centro de Costo', required=True, tracking=True)
    obra_id = fields.Many2one(related='project_id.account_id', string='Contabilidad Analítica', tracking=True)
    tipo_contrato = fields.Many2one(related='partner_id.tipo_contratista', string='Tipo de Contrato')
    company_id = fields.Many2one('res.company', string='Empresa', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    monto_contratado = fields.Monetary(string='Monto Contratado (s/IVA)', required=True, tracking=True)
    porcentaje_anticipo = fields.Float(string='% Anticipo', default=20.0, tracking=True)
    monto_anticipo = fields.Monetary(string='Monto Anticipo', compute='_compute_anticipo', store=True)
    retencion_fondo_garantia = fields.Boolean(string='Aplica Fondo de Garantía', default=True, tracking=True)
    porcentaje_retencion = fields.Float(string='% Retención Garantía', default=5.0, tracking=True)
    expediente_completo = fields.Boolean(related='partner_id.expediente_completo', string='Expediente Validado')
    expediente_digital = fields.One2many(related='partner_id.expediente_digital', string='Expediente digital')
    finicio = fields.Date(string='Fecha de inicio')
    ffin = fields.Date(string='Fecha de termino')
    ffirma = fields.Date(string='Fecha de firma del contrato') 
    lfirma = fields.Char(string='Lugar de firma del contrato')
    plazo = fields.Char(string='Plazo de la garantía')
    penalizacion = fields.Char(string='Penalización')
    dias = fields.Integer(string='Días para subsanar')
    testigo1 = fields.Char(string='Testigo 1')
    testigo2 = fields.Char(string='Testigo 2')
    description = fields.Char(string='Descripción de los trabajos realizados')
    # T0120: N3 emite y solicita el Vo.Bo.; N2 o N1 lo otorgan. Sin Vo.Bo. el contrato no se firma ni pasa a estimaciones.
    modalidad = fields.Selection([('alzado', 'Precio Alzado'), ('unitario', 'Precios Unitarios'), ('adminitracion', 'Administración de Obra')], 
        string='Modalidad de Pago', required=True, tracking=True)
    medio = fields.Selection([('transferencia', 'Transferencia bancaria'), ('otro', 'Otro medio acordado')], 
        string='Medio de Pago', required=True, tracking=True)
    diaspago = fields.Integer(string='Días para pagar')
    suministro = fields.Selection([('contratista', 'El Contratista'), ('subcontratista', 'El Subcontratista'), ('ambos', 'Ambos, según el presupuesto')], 
        string='Medio de Pago', required=True, tracking=True)
    state = fields.Selection([('draft', 'Borrador'), ('in_approval', 'En espera de Vo.Bo. de Dirección'), ('active', 'Activo / Firmado'),
        ('done', 'Finiquitado'), ('cancel', 'Cancelado')], string='Estatus', default='draft', required=True, tracking=True,
        group_expand='_group_expand_states')

    _sql_constraints = [('name_uniq', 'unique(name)', 'El folio del contrato debe ser único.')]

    def _group_expand_states(self, states, domain):
        return [key for key, val in self._fields['state'].selection]

    @api.depends('monto_contratado', 'porcentaje_anticipo')
    def _compute_anticipo(self):
        for rec in self:
            rec.monto_anticipo = rec.monto_contratado * (rec.porcentaje_anticipo / 100.0)

    @api.constrains('monto_contratado', 'porcentaje_anticipo', 'porcentaje_retencion')
    def _check_montos(self):
        for rec in self:
            if rec.monto_contratado <= 0:
                raise ValidationError(_('El monto contratado debe ser mayor a cero.'))
            if not 0 <= rec.porcentaje_anticipo <= 100 or not 0 <= rec.porcentaje_retencion <= 100:
                raise ValidationError(_('Los porcentajes de anticipo y de retención deben estar entre 0 y 100.'))

    @api.constrains('state', 'partner_id')
    def _check_expediente(self):
        # Gobernanza: ningún contrato pasa a aprobación ni se activa con el expediente incompleto, venga de un botón, del kanban o de código
        for rec in self:
            if rec.state in ('done') and not rec.partner_id.expediente_completo:
                raise ValidationError(_('El expediente digital de %s está incompleto. Cargue todos los documentos requeridos antes de continuar.', rec.partner_id.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('gestion.obra.contrato') or _('Nuevo')
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('state') == 'in_approval':
            exigir_nivel(self.env, NIVEL_3, 'solicitar el Vo.Bo. de Dirección')
        if vals.get('state') == 'active':
            exigir_nivel(self.env, NIVEL_2, 'otorgar el Vo.Bo. de Dirección al contrato')
        return super().write(vals)

    def unlink(self):
        if any(rec.state not in ('draft', 'cancel') for rec in self):
            raise UserError(_('Solo se pueden eliminar contratos en Borrador o Cancelados.'))
        return super().unlink()

    def action_solicitar_aprobacion(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Solo se puede solicitar el Vo.Bo. de un contrato en Borrador.'))

            if not rec.partner_id.email:
                self._post_html(_('El subcontratista no cuenta con email.'))
            else:
                emails.add(rec.partner_id.email.strip())
                correos_list = sorted(e for e in emails if '@' in e)
                template = self.env.ref('gestion_obras.mail_tmpl_expediente_subcontratista', raise_if_not_found=False)                                                                              
                if not correos_list:
                    self._post_html(_('El subcontratista no cuenta con email.'))
                if not template:
                    raise ValidationError(_('No se encontró la plantilla de correo.'))

                try:
                    correos = ', '.join(correos_list)
                    email_values = {'model': 'gestion.obra.contrato', 'email_to': correos}
                    template.send_mail(rec.id, force_send=True, email_values=email_values)
                    self._post_html(_('Se envió correo a: ') + correos)
                except Exception:
                    self._post_html(_('Error al enviar el correo'))

            rec.state = 'in_approval'

    def action_activar_contrato(self):
        for rec in self:
            if rec.state != 'in_approval':
                raise UserError(_('Solo se otorga el Vo.Bo. a un contrato En espera de Vo.Bo. de Dirección.'))
            rec.state = 'active'

    def action_finiquitar(self):
        for rec in self:
            if rec.state != 'active':
                raise UserError(_('Solo se puede finiquitar un contrato Activo.'))
            rec.state = 'done'

    def action_cancelar(self):
        for rec in self:
            if rec.state not in ('draft', 'in_approval'):
                raise UserError(_('Solo se puede cancelar un contrato en Borrador o En espera de Vo.Bo.'))
            rec.state = 'cancel'

    def action_borrador(self):
        for rec in self:
            if rec.state != 'cancel':
                raise UserError(_('Solo un contrato Cancelado puede regresar a Borrador.'))
            rec.state = 'draft'

    def action_ver_expediente(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'res.partner', 'res_id': self.partner_id.id, 'view_mode': 'form', 'target': 'current'}

    def imprimir_contrato(self):
        domicilio = (self.project_id.street if self.project_id.street else '' + ' ' + self.project_id.col if self.project_id.col else '' + ' ' + 
            self.project_id.zip if self.project_id.zip else '').strip()
        """if not self.expediente_completo:
            raise ValidationError(_('El expediente digital está incompleto. Cargue todos los documentos requeridos antes de continuar.'))
        if domicilio == '':
            raise ValidationError(_('La obra no cuenta con domicilio favor de notificar al área correspondiente'))  """

        return self.env.ref('gestion_obras.action_report_contrato_template').report_action(self)


    def get_importe_en_letra(self, numero):
        self.ensure_one()
        currency = self.currency_id
        entero = int(numero)
        decimal = round(numero - entero, 2)
        importe = currency.amount_to_text(entero).upper()
        if importe == 'UNO PESOS':
            importe = 'UN PESO'
        
        importe = importe.replace('UNO PESOS', 'UN PESOS') + ' ' + str(decimal).split('.')[1] + '/100 M.N.'
        return importe
