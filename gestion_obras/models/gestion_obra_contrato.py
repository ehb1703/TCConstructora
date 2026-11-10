# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class GestionObraContrato(models.Model):
    _name = 'gestion.obra.contrato'
    _description = 'Contrato y Subcontrato de Obra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Folio de Contrato', required=True, readonly=True, copy=False, default=lambda self: _('Nuevo'))
    partner_id = fields.Many2one('res.partner', string='Contratista / Proveedor', required=True, tracking=True,
        domain="[('expediente_completo', '=', True)]", help='Solo se pueden elegir contactos con el expediente digital completo.')
    obra_id = fields.Many2one('account.analytic.account', string='Obra / Centro de Costo', required=True, tracking=True)
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
    state = fields.Selection([('draft', 'Borrador'), ('in_approval', 'En Aprobación Operaciones'), ('active', 'Activo / Firmado'),
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
            if rec.state in ('in_approval', 'active') and not rec.partner_id.expediente_completo:
                raise ValidationError(_('El expediente digital de %s está incompleto. Cargue todos los documentos requeridos antes de continuar.', rec.partner_id.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('gestion.obra.contrato') or _('Nuevo')
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('state') == 'active' and not self.env.su and not self.env.user.has_group('gestion_obras.group_activar_contrato'):
            raise UserError(_('No tiene permiso para activar contratos.'))
        return super().write(vals)

    def unlink(self):
        if any(rec.state not in ('draft', 'cancel') for rec in self):
            raise UserError(_('Solo se pueden eliminar contratos en Borrador o Cancelados.'))
        return super().unlink()

    def action_solicitar_aprobacion(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Solo se puede solicitar aprobación de un contrato en Borrador.'))
            if not rec.partner_id.expediente_completo:
                raise ValidationError(_('No se puede enviar a aprobación. El expediente digital del contratista está incompleto.'))
            rec.state = 'in_approval'

    def action_activar_contrato(self):
        for rec in self:
            if rec.state != 'in_approval':
                raise UserError(_('Solo se puede activar un contrato En Aprobación.'))
            rec.state = 'active'

    def action_finiquitar(self):
        for rec in self:
            if rec.state != 'active':
                raise UserError(_('Solo se puede finiquitar un contrato Activo.'))
            rec.state = 'done'

    def action_cancelar(self):
        for rec in self:
            if rec.state not in ('draft', 'in_approval'):
                raise UserError(_('Solo se puede cancelar un contrato en Borrador o En Aprobación.'))
            rec.state = 'cancel'

    def action_borrador(self):
        for rec in self:
            if rec.state != 'cancel':
                raise UserError(_('Solo un contrato Cancelado puede regresar a Borrador.'))
            rec.state = 'draft'

    def action_ver_expediente(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'res.partner', 'res_id': self.partner_id.id, 'view_mode': 'form', 'target': 'current'}