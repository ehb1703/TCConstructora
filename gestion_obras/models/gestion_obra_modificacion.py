# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

GRUPO_TECNICO = 'gestion_obras.group_aprobacion_tecnica'
GRUPO_DIRECCION = 'gestion_obras.group_aprobacion_direccion'


class GestionObraModificacion(models.Model):
    _name = 'gestion.obra.modificacion'
    _description = 'Aditivas, Deductivas y Órdenes de Cambio'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Folio Cambio', required=True, readonly=True, copy=False, default=lambda self: _('Nuevo'))
    presupuesto_id = fields.Many2one('gestion.obra.presupuesto', string='Presupuesto Control', required=True, tracking=True,
        domain="[('state', '=', 'approved')]")
    obra_id = fields.Many2one(related='presupuesto_id.obra_id', string='Obra', store=True)
    currency_id = fields.Many2one(related='presupuesto_id.currency_id', string='Moneda')
    tipo_movimiento = fields.Selection([('aditiva', 'Aditiva (Incremento)'), ('deductiva', 'Deductiva (Reducción)'),
        ('orden_cambio', 'Traspaso entre Partidas'), ('extraordinario', 'Concepto Extraordinario')], string='Tipo de Movimiento', required=True, tracking=True)
    linea_ids = fields.One2many('gestion.obra.modificacion.linea', 'modificacion_id', string='Desglose', copy=True)
    monto_total_afectacion = fields.Monetary(string='Impacto Financiero Total ($)', compute='_compute_monto_total', store=True,
        help='Aditivas, deductivas y extraordinarios: suma del desglose. Traspasos: monto reasignado (el total global no cambia).')
    ampliacion_plazo_dias = fields.Integer(string='Ampliación de Plazo (Días)', tracking=True)
    justificacion = fields.Text(string='Memoria Descriptiva / Justificación Técnica', required=True)
    folio_bitacora = fields.Char(string='Folio Bitácora de Obra', tracking=True)
    state = fields.Selection([('draft', 'Borrador'), ('pending_tech', 'Aprobación Técnica'), ('pending_dir', 'Aprobación Dirección'),
        ('approved', 'Autorizado / Aplicado'), ('rejected', 'Rechazado')], string='Estatus', default='draft', required=True, tracking=True, copy=False)
    aprobo_tecnico_id = fields.Many2one('res.users', string='Aprobó (técnica)', readonly=True, copy=False)
    aprobo_direccion_id = fields.Many2one('res.users', string='Aprobó (dirección)', readonly=True, copy=False)

    @api.depends('tipo_movimiento', 'linea_ids.monto')
    def _compute_monto_total(self):
        for rec in self:
            montos = rec.linea_ids.mapped('monto')
            rec.monto_total_afectacion = sum(m for m in montos if m > 0) if rec.tipo_movimiento == 'orden_cambio' else sum(montos)

    @api.constrains('ampliacion_plazo_dias')
    def _check_plazo(self):
        for rec in self:
            if rec.ampliacion_plazo_dias < 0:
                raise ValidationError(_('La ampliación de plazo no puede ser negativa.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('gestion.obra.modificacion') or _('Nuevo')
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            if vals.get('state') == 'pending_dir' and not self.env.user.has_group(GRUPO_TECNICO):
                raise UserError(_('No tiene permiso de aprobación técnica.'))
            if vals.get('state') == 'approved' and not self.env.user.has_group(GRUPO_DIRECCION):
                raise UserError(_('No tiene permiso de aprobación de dirección.'))
            cerradas = self.filtered(lambda m: m.state in ('approved', 'rejected'))
            if cerradas and set(vals) - {'state', 'message_main_attachment_id'} and not self.env.context.get('gestion_obras_sistema'):
                raise UserError(_('Una modificación autorizada o rechazada no se puede editar.'))
        return super().write(vals)

    def unlink(self):
        if any(rec.state not in ('draft', 'rejected') for rec in self):
            raise UserError(_('Solo se pueden eliminar modificaciones en Borrador o Rechazadas.'))
        return super().unlink()

    def _validar_desglose(self):
        """Reglas del tipo de movimiento. Se revisan al enviar y otra vez al autorizar."""
        self.ensure_one()
        if self.presupuesto_id.state != 'approved':
            raise UserError(_('El presupuesto %s no tiene la base aprobada; las modificaciones solo aplican sobre la base congelada.', self.presupuesto_id.name))
        if not self.linea_ids:
            raise UserError(_('Capture el desglose de la modificación.'))
        moneda = self.currency_id
        if self.tipo_movimiento == 'extraordinario':
            for linea in self.linea_ids:
                if not linea.product_id or not linea.product_id.default_code:
                    raise UserError(_('Un extraordinario requiere el desglose por insumo con referencia interna (línea: %s).', linea.descripcion or '-'))
        elif any(not linea.partida_id for linea in self.linea_ids):
            raise UserError(_('Indique la partida afectada en cada línea del desglose.'))
        if self.tipo_movimiento == 'orden_cambio':
            if not (any(moneda.compare_amounts(m, 0) < 0 for m in self.linea_ids.mapped('monto'))
                    and any(moneda.compare_amounts(m, 0) > 0 for m in self.linea_ids.mapped('monto'))):
                raise UserError(_('Un traspaso necesita al menos una partida que cede saldo (monto negativo) y una que lo recibe (monto positivo).'))
            if not moneda.is_zero(sum(self.linea_ids.mapped('monto'))):
                raise UserError(_('Un traspaso debe ser neutro: el desglose suma %s y debe sumar cero.', sum(self.linea_ids.mapped('monto'))))
        elif any(moneda.compare_amounts(m, 0) <= 0 for m in self.linea_ids.mapped('monto')):
            raise UserError(_('En aditivas, deductivas y extraordinarios la cantidad y el precio unitario deben ser positivos.'))
        if self.tipo_movimiento in ('deductiva', 'orden_cambio'):
            for partida in self.linea_ids.partida_id:
                efecto = sum(self.linea_ids.filtered(lambda l: l.partida_id == partida).mapped('monto_efecto'))
                if moneda.compare_amounts(partida.monto_control + efecto, 0) < 0:
                    raise UserError(_('La partida %(p)s quedaría con saldo negativo (control %(c)s, movimiento %(m)s).',
                                      p=partida.name, c=partida.monto_control, m=efecto))

    def action_enviar(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Solo se envía a aprobación una modificación en Borrador.'))
            rec._validar_desglose()
            rec.state = 'pending_tech'

    def action_aprobar_tecnico(self):
        for rec in self:
            if rec.state != 'pending_tech':
                raise UserError(_('La modificación no está en Aprobación Técnica.'))
            rec.write({'state': 'pending_dir', 'aprobo_tecnico_id': self.env.user.id})

    def action_aprobar_direccion(self):
        for rec in self:
            if rec.state != 'pending_dir':
                raise UserError(_('La modificación no está en Aprobación de Dirección.'))
            rec._validar_desglose()
            if rec.tipo_movimiento == 'extraordinario':
                partida = rec.presupuesto_id._partida_extraordinarios()
                rec.linea_ids.with_context(gestion_obras_sistema=True).write({'partida_id': partida.id})
            rec.write({'state': 'approved', 'aprobo_direccion_id': self.env.user.id})

    def action_rechazar(self):
        for rec in self:
            if rec.state not in ('pending_tech', 'pending_dir'):
                raise UserError(_('Solo se rechaza una modificación en aprobación.'))
            grupo = GRUPO_TECNICO if rec.state == 'pending_tech' else GRUPO_DIRECCION
            if not self.env.su and not self.env.user.has_group(grupo):
                raise UserError(_('No tiene permiso para rechazar esta modificación en su etapa actual.'))
            rec.state = 'rejected'

    def action_borrador(self):
        for rec in self:
            if rec.state != 'rejected':
                raise UserError(_('Solo una modificación rechazada regresa a Borrador.'))
            rec.with_context(gestion_obras_sistema=True).write({'state': 'draft', 'aprobo_tecnico_id': False, 'aprobo_direccion_id': False})


class GestionObraModificacionLinea(models.Model):
    _name = 'gestion.obra.modificacion.linea'
    _description = 'Desglose de modificación presupuestal'

    modificacion_id = fields.Many2one('gestion.obra.modificacion', string='Modificación', required=True, ondelete='cascade')
    presupuesto_id = fields.Many2one(related='modificacion_id.presupuesto_id', string='Presupuesto')
    tipo_movimiento = fields.Selection(related='modificacion_id.tipo_movimiento', string='Tipo')
    currency_id = fields.Many2one(related='modificacion_id.currency_id', string='Moneda')
    partida_id = fields.Many2one('gestion.obra.partida', string='Partida', ondelete='restrict', domain="[('presupuesto_id', '=', presupuesto_id)]")
    product_id = fields.Many2one('product.product', string='Insumo')
    descripcion = fields.Char(string='Descripción')
    cantidad = fields.Float(string='Cantidad', digits='Product Unit of Measure',
        help='Volumen que se agrega o reduce. En traspasos, negativa en la partida que cede saldo.')
    precio_unitario = fields.Monetary(string='P.U.', help='Para un ajuste de precio: cantidad afectada por la diferencia de precio unitario.')
    monto = fields.Monetary(string='Importe', compute='_compute_monto', store=True)
    monto_efecto = fields.Monetary(string='Efecto en la partida', compute='_compute_monto', store=True)

    @api.depends('cantidad', 'precio_unitario', 'modificacion_id.tipo_movimiento')
    def _compute_monto(self):
        for line in self:
            line.monto = line.cantidad * line.precio_unitario
            line.monto_efecto = -line.monto if line.tipo_movimiento == 'deductiva' else line.monto

    def _bloqueada(self):
        return not self.env.context.get('gestion_obras_sistema') and any(l.modificacion_id.state != 'draft' for l in self)

    @api.model_create_multi
    def create(self, vals_list):
        lineas = super().create(vals_list)
        if lineas._bloqueada():
            raise UserError(_('El desglose solo se captura con la modificación en Borrador.'))
        return lineas

    def write(self, vals):
        if self._bloqueada():
            raise UserError(_('El desglose solo se edita con la modificación en Borrador.'))
        return super().write(vals)

    def unlink(self):
        if self._bloqueada():
            raise UserError(_('El desglose solo se edita con la modificación en Borrador.'))
        return super().unlink()
