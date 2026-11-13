# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .seguridad import NIVEL_1, NIVEL_2, NIVEL_4, exigir_nivel

PARTIDA_EXTRAORDINARIOS = 'EXTRAORDINARIOS'
CAMPOS_BASE_PARTIDA = {'presupuesto_id', 'name', 'es_extraordinario', 'product_id', 'cantidad_base', 'precio_unitario_base'}


class GestionObraPresupuesto(models.Model):
    _name = 'gestion.obra.presupuesto'
    _description = 'Presupuesto Control de Obra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Nombre Presupuesto', required=True, tracking=True)
    obra_id = fields.Many2one('account.analytic.account', string='Obra / Proyecto', required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    # T0120: N4 captura y envía a revisión; N2 aprueba en lo operativo; N1 aprueba en definitiva y congela la base
    state = fields.Selection([('draft', 'Borrador'), ('in_revision', 'En Revisión Técnica'), ('op_approved', 'Aprobación Operativa'),
        ('approved', 'Base Aprobada (Congelada)')], string='Estatus', default='draft', required=True, tracking=True)
    fecha_congelamiento = fields.Datetime(string='Fecha de congelamiento', readonly=True, copy=False)
    partida_ids = fields.One2many('gestion.obra.partida', 'presupuesto_id', string='Partidas')
    modificacion_ids = fields.One2many('gestion.obra.modificacion', 'presupuesto_id', string='Órdenes de Cambio / Aditivas')
    modificacion_count = fields.Integer(string='Modificaciones', compute='_compute_modificacion_count')
    monto_base_original = fields.Monetary(string='Presupuesto Base (Original)', compute='_compute_totales', store=True,
        help='Suma de las partidas del presupuesto base. Se congela al aprobar la base: solo cambia por medio de modificaciones.')
    monto_aditivas_acum = fields.Monetary(string='Aditivas Acumuladas', compute='_compute_totales', store=True)
    monto_deductivas_acum = fields.Monetary(string='Deductivas Acumuladas', compute='_compute_totales', store=True)
    monto_presupuesto_control = fields.Monetary(string='Presupuesto Control', compute='_compute_totales', store=True)
    monto_comprometido_oc = fields.Monetary(string='Monto Comprometido en Compras', compute='_compute_comprometido',
        help='Órdenes de compra confirmadas con distribución analítica a la obra, más contratos activos o finiquitados de la obra.')
    saldo_disponible_compras = fields.Monetary(string='Saldo Disponible Compras', compute='_compute_comprometido')

    _sql_constraints = [('obra_uniq', 'unique(obra_id)', 'Ya existe un presupuesto para esta obra.')]

    @api.depends('partida_ids.monto_total_partida', 'partida_ids.es_extraordinario', 'modificacion_ids.state',
                 'modificacion_ids.tipo_movimiento', 'modificacion_ids.monto_total_afectacion')
    def _compute_totales(self):
        for rec in self:
            aplicadas = rec.modificacion_ids.filtered(lambda m: m.state == 'approved')
            aditivas = sum(aplicadas.filtered(lambda m: m.tipo_movimiento in ('aditiva', 'extraordinario')).mapped('monto_total_afectacion'))
            deductivas = sum(aplicadas.filtered(lambda m: m.tipo_movimiento == 'deductiva').mapped('monto_total_afectacion'))
            rec.monto_base_original = sum(rec.partida_ids.filtered(lambda p: not p.es_extraordinario).mapped('monto_total_partida'))
            rec.monto_aditivas_acum = aditivas
            rec.monto_deductivas_acum = deductivas
            rec.monto_presupuesto_control = rec.monto_base_original + aditivas - deductivas

    def _compute_comprometido(self):
        lineas = self.env['purchase.order.line'].sudo().search([('order_id.state', 'in', ('purchase', 'done')), ('analytic_distribution', '!=', False)])
        contratos = self.env['gestion.obra.contrato'].sudo().search([('obra_id', 'in', self.obra_id.ids), ('state', 'in', ('active', 'done'))])
        for rec in self:
            cuenta = str(rec.obra_id.id)
            total = 0.0
            for linea in lineas:
                # las llaves de la distribución pueden combinar cuentas de varios planes ("12,34")
                porcentaje = sum(p for llave, p in (linea.analytic_distribution or {}).items() if cuenta in llave.split(','))
                if porcentaje:
                    subtotal = linea.currency_id._convert(linea.price_subtotal, rec.currency_id, rec.company_id, linea.order_id.date_order or fields.Date.today())
                    total += subtotal * porcentaje / 100.0
            total += sum(contratos.filtered(lambda c: c.obra_id == rec.obra_id).mapped('monto_contratado'))
            rec.monto_comprometido_oc = total
            rec.saldo_disponible_compras = rec.monto_presupuesto_control - total

    def _compute_modificacion_count(self):
        for rec in self:
            rec.modificacion_count = len(rec.modificacion_ids)

    # Nivel que exige cada estado destino: ni desde el kanban ni por código se salta la matriz de autorizaciones
    NIVEL_POR_ESTADO = {'in_revision': (NIVEL_4, 'enviar el presupuesto a revisión técnica'), 'op_approved': (NIVEL_2, 'dar la aprobación operativa del presupuesto'),
                        'approved': (NIVEL_1, 'aprobar y congelar el presupuesto base'), 'draft': (NIVEL_2, 'regresar el presupuesto a Borrador')}

    def write(self, vals):
        if {'obra_id', 'company_id'} & set(vals) and any(rec.state == 'approved' for rec in self):
            raise UserError(_('La obra de un presupuesto con la base congelada no se puede cambiar.'))
        if vals.get('state') in self.NIVEL_POR_ESTADO and any(rec.state != vals['state'] for rec in self):
            exigir_nivel(self.env, *self.NIVEL_POR_ESTADO[vals['state']])
        return super().write(vals)

    def unlink(self):
        if any(rec.state == 'approved' for rec in self):
            raise UserError(_('Un presupuesto con la base congelada no se puede eliminar.'))
        return super().unlink()

    def action_enviar_revision(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Solo se envía a revisión técnica un presupuesto en Borrador.'))
            if not rec.partida_ids.filtered(lambda p: not p.es_extraordinario):
                raise UserError(_('Capture al menos una partida antes de enviar el presupuesto a revisión.'))
            rec.state = 'in_revision'

    def action_aprobar_operativo(self):
        for rec in self:
            if rec.state != 'in_revision':
                raise UserError(_('Solo se aprueba en lo operativo un presupuesto En Revisión Técnica.'))
            rec.state = 'op_approved'

    def action_aprobar_base(self):
        for rec in self:
            if rec.state != 'op_approved':
                raise UserError(_('El presupuesto necesita la Aprobación Operativa (Nivel 2) antes de la aprobación definitiva.'))
            if not rec.partida_ids.filtered(lambda p: not p.es_extraordinario):
                raise UserError(_('Capture al menos una partida antes de aprobar el presupuesto base.'))
            rec.write({'state': 'approved', 'fecha_congelamiento': fields.Datetime.now()})
            rec._partida_extraordinarios()

    def action_regresar_borrador(self):
        for rec in self:
            if rec.state not in ('in_revision', 'op_approved'):
                raise UserError(_('Solo regresa a Borrador un presupuesto En Revisión o con Aprobación Operativa; la base congelada solo cambia con modificaciones.'))
            rec.state = 'draft'

    def _partida_extraordinarios(self):
        # Partida obligatoria donde se alojan los conceptos e insumos no previstos. Se abre al congelar la base.
        self.ensure_one()
        partida = self.partida_ids.filtered(lambda p: p.es_extraordinario and p.name == PARTIDA_EXTRAORDINARIOS)[:1]
        if not partida:
            partida = self.env['gestion.obra.partida'].with_context(gestion_obras_sistema=True).create({
                'presupuesto_id': self.id, 'name': PARTIDA_EXTRAORDINARIOS, 'es_extraordinario': True, 'sequence': 9999})
        return partida

    def action_ver_modificaciones(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Modificaciones'), 'res_model': 'gestion.obra.modificacion',
                'view_mode': 'list,form', 'domain': [('presupuesto_id', '=', self.id)], 'context': {'default_presupuesto_id': self.id}}


class GestionObraPartida(models.Model):
    _name = 'gestion.obra.partida'
    _description = 'Partida Presupuestal e Insumos'
    _order = 'presupuesto_id, sequence, id'

    presupuesto_id = fields.Many2one('gestion.obra.presupuesto', string='Presupuesto', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Secuencia', default=10)
    name = fields.Char(string='Nombre de Partida / Concepto', required=True)
    es_extraordinario = fields.Boolean(string='Es Partida Extraordinario', default=False)
    product_id = fields.Many2one('product.product', string='Insumo (Referencia Única)')
    default_code = fields.Char(related='product_id.default_code', string='Ref. Interna')
    currency_id = fields.Many2one(related='presupuesto_id.currency_id', string='Moneda')
    cantidad_base = fields.Float(string='Cantidad Base', digits='Product Unit of Measure')
    precio_unitario_base = fields.Monetary(string='P.U. Base')
    monto_total_partida = fields.Monetary(string='Monto Base', compute='_compute_monto', store=True)
    linea_ids = fields.One2many('gestion.obra.modificacion.linea', 'partida_id', string='Movimientos')
    monto_modificaciones = fields.Monetary(string='Modificaciones', compute='_compute_control', store=True,
        help='Efecto neto de las aditivas, deductivas, extraordinarios y traspasos autorizados sobre la partida.')
    monto_control = fields.Monetary(string='Monto Control', compute='_compute_control', store=True)

    @api.depends('cantidad_base', 'precio_unitario_base')
    def _compute_monto(self):
        for line in self:
            line.monto_total_partida = line.cantidad_base * line.precio_unitario_base

    @api.depends('monto_total_partida', 'linea_ids.monto_efecto', 'linea_ids.modificacion_id.state')
    def _compute_control(self):
        for line in self:
            line.monto_modificaciones = sum(line.linea_ids.filtered(lambda l: l.modificacion_id.state == 'approved').mapped('monto_efecto'))
            line.monto_control = line.monto_total_partida + line.monto_modificaciones

    @api.constrains('cantidad_base', 'precio_unitario_base')
    def _check_base(self):
        for line in self:
            if line.cantidad_base < 0 or line.precio_unitario_base < 0:
                raise ValidationError(_('La cantidad y el precio unitario base no pueden ser negativos (partida %s).', line.name))

    def _congelada(self):
        return not self.env.context.get('gestion_obras_sistema') and any(p.presupuesto_id.state == 'approved' for p in self)

    @api.model_create_multi
    def create(self, vals_list):
        partidas = super().create(vals_list)
        if partidas._congelada():
            raise UserError(_('El presupuesto base está congelado. Para agregar conceptos registre una Aditiva o un Extraordinario.'))
        return partidas

    def write(self, vals):
        if CAMPOS_BASE_PARTIDA & set(vals) and self._congelada():
            raise UserError(_('El presupuesto base está congelado: ninguna partida se puede editar. Registre una Aditiva, Deductiva u Orden de Cambio.'))
        return super().write(vals)

    def unlink(self):
        if any(p.presupuesto_id.state == 'approved' for p in self):
            raise UserError(_('El presupuesto base está congelado: ninguna partida se puede eliminar. Registre una Deductiva u Orden de Cambio.'))
        return super().unlink()
