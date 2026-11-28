# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

TIPOS_REQUERIMIENTO = [('ordinario', 'Ordinario'), ('extraordinario', 'Extraordinario')]
# Matriz de validaciones, Residente de Obra: "seleccionar el motivo (Cambio de especificación, Solicitud del cliente, Ajuste en sitio)";
# con "Otro" el residente escribe el motivo
MOTIVOS = [('cambio_especificacion', 'Cambio de especificación'), ('solicitud_cliente', 'Solicitud del cliente'),
           ('ajuste_sitio', 'Ajuste en sitio'), ('otro', 'Otro')]
# El proceso anterior escribía estos estados; se traducen a los de la especificación
ESTADOS_ANTERIORES = {'send': 'in_approval', 'aprobado': 'sent_purchase'}
GRUPO_COSTOS = 'requisition_residents.group_costos'


class RequisitionMaterials(models.Model):
    _inherit = 'requisition.materials'

    # Estados de la especificación (Alcance - Flujo de Aprobaciones)
    state = fields.Selection(selection=[('draft', 'Borrador'), ('in_approval', 'En Autorización'), ('approved', 'Autorizado'),
                                        ('sent_purchase', 'Enviado a Compras')], string='Estatus', default='draft', tracking=True)
    # Catálogo de campos: Proyecto Global (encabezado). Es la misma obra de la requisición.
    x_proyecto_id = fields.Many2one('project.project', string='Proyecto Global', related='project_id', store=True, readonly=False,
        help='Identifica la obra o desarrollo general que agrupa frentes o contratos independientes.')
    # Regla 3: la requisición es extraordinaria si alguna de sus líneas lo es
    x_tipo_requerimiento = fields.Selection(TIPOS_REQUERIMIENTO, string='Tipo de Requerimiento', compute='_compute_x_tipo_requerimiento',
        store=True)
    x_orden_cambio_id = fields.Many2one('gestion.obra.modificacion', string='Orden de Cambio', tracking=True,
        help='Orden de Cambio que respalda los insumos extraordinarios (o adjunte el Dictamen Técnico firmado).')
    x_orden_ids = fields.Many2many('purchase.order', string='Órdenes de compra', compute='_compute_x_orden_ids')

    @api.depends('line_ids.x_tipo_requerimiento')
    def _compute_x_tipo_requerimiento(self):
        for rec in self:
            extra = any(l.x_tipo_requerimiento == 'extraordinario' for l in rec.line_ids)
            rec.x_tipo_requerimiento = 'extraordinario' if extra else 'ordinario'

    def _compute_x_orden_ids(self):
        for rec in self:
            rec.x_orden_ids = rec.oc_ids | rec.line_ids.mapped('x_compra_line_ids.order_id')

    def write(self, vals):
        if vals.get('state') in ESTADOS_ANTERIORES:
            vals = dict(vals, state=ESTADOS_ANTERIORES[vals['state']])
        return super().write(vals)

    def _correos_grupo(self, xmlid):
        grupo = self.env.ref(xmlid, raise_if_not_found=False)
        usuarios = grupo.users.filtered(lambda u: u.active and u.partner_id.email) if grupo else self.env['res.users']
        return sorted({u.partner_id.email.strip() for u in usuarios if '@' in u.partner_id.email})

    def action_send(self):
        # Borrador -> En Autorización: avisa a Costos, que es quien autoriza (Regla 3: "Autorizado por Costos")
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Solo se envían a autorización las requisiciones en Borrador.'))
            if not rec.line_ids:
                raise UserError(_('Agregue al menos un insumo a la requisición.'))
            correos = rec._correos_grupo(GRUPO_COSTOS)
            template = self.env.ref('requisition_residents.mail_tmpl_requisition_materials_solicitud', raise_if_not_found=False)
            try:
                if template and correos:
                    # Aviso automático: se arma con permisos de sistema (el residente puede no tener lectura de la obra en el correo)
                    template.sudo().send_mail(rec.id, force_send=True, email_values={'model': 'requisition_materials', 'email_to': ', '.join(correos)})
                    rec._post_html(_('Se envió correo a Costos: ') + ', '.join(correos))
            except Exception:
                rec._post_html(_('Error al enviar el correo'))
            rec.state = 'in_approval'

    def _exigir_costos(self):
        if not (self.env.user.has_group(GRUPO_COSTOS) or self.env.user.has_group('base.group_system')):
            raise UserError(_('Solo Costos puede autorizar o rechazar requisiciones.'))

    def action_autorizar(self):
        # En Autorización -> Autorizado (por Costos) -> Enviado a Compras (automático). Las reglas automatizadas de la
        # especificación se ejecutan al guardar cada estado (Regla 3 al pasar a Autorizado).
        self._exigir_costos()
        for rec in self:
            if rec.state != 'in_approval':
                raise UserError(_('Solo se autorizan requisiciones En Autorización.'))
            rec.state = 'approved'
            rec.state = 'sent_purchase'
            rec._post_html(_('Autorizada por Costos y enviada a Compras para su consolidación.'))

    def action_rechazar(self):
        self._exigir_costos()
        for rec in self:
            if rec.state != 'in_approval':
                raise UserError(_('Solo se rechazan requisiciones En Autorización.'))
            rec.state = 'draft'
            rec._post_html(_('Rechazada por Costos: regresa a Borrador para su corrección.'))

    def action_confirm(self):
        # El proceso anterior generaba cotizaciones al aprobar; ahora Compras las genera al consolidar
        return self.action_autorizar()

    def action_regresar_borrador(self):
        for rec in self:
            consolidadas = rec.line_ids.mapped('x_compra_line_ids.order_id')
            if consolidadas:
                raise UserError(_('No se puede regresar a Borrador: Compras ya consolidó sus insumos en %s.')
                                % ', '.join(consolidadas.mapped('name')))
        return super().action_regresar_borrador()


class RequisitionMaterialsLine(models.Model):
    _inherit = 'requisition.materials.line'

    x_proyecto_id = fields.Many2one(related='req_id.project_id', string='Proyecto Global', store=True)
    state = fields.Selection(related='req_id.state', string='Estatus', store=True)
    x_frente_id = fields.Many2one('account.analytic.account', string='Bloque / Frente / Contrato', index=True,
        help='Define el frente de obra o contrato específico al que se imputa la recepción y el costo del insumo.')
    x_tipo_requerimiento = fields.Selection(TIPOS_REQUERIMIENTO, string='Tipo de Requerimiento', default='ordinario', required=True,
        help='Clasifica si la solicitud corresponde a insumos previstos en el catálogo base o a una aditiva/extra.')
    x_motivo_tipo = fields.Selection(MOTIVOS, string='Motivo')
    x_motivo_extraordinario = fields.Text(string='Motivo Extraordinario',
        help='Justificación técnica de la necesidad extraordinaria (mínimo 15 caracteres).')
    x_compra_line_ids = fields.Many2many('purchase.order.line', 'requisicion_materiales_compra_rel', 'requisicion_line_id', 'compra_line_id',
        string='Líneas de compra', copy=False)
    x_atendida_anterior = fields.Boolean(string='Atendida por el proceso anterior', copy=False)
    x_pendiente_cotizar = fields.Boolean(string='Pendiente de cotizar', compute='_compute_x_pendiente_cotizar', store=True)

    @api.depends('state', 'x_compra_line_ids', 'x_atendida_anterior')
    def _compute_x_pendiente_cotizar(self):
        for line in self:
            line.x_pendiente_cotizar = line.state == 'sent_purchase' and not line.x_compra_line_ids and not line.x_atendida_anterior

    @api.onchange('x_motivo_tipo')
    def _onchange_x_motivo_tipo(self):
        if self.x_motivo_tipo and self.x_motivo_tipo != 'otro':
            self.x_motivo_extraordinario = dict(MOTIVOS)[self.x_motivo_tipo]
        elif self.x_motivo_tipo == 'otro' and self.x_motivo_extraordinario in dict(MOTIVOS).values():
            self.x_motivo_extraordinario = False

    @api.onchange('x_tipo_requerimiento')
    def _onchange_x_tipo_requerimiento(self):
        if self.x_tipo_requerimiento != 'extraordinario':
            self.x_motivo_tipo = False
            self.x_motivo_extraordinario = False

    @api.model
    def _motivo_desde_lista(self, vals):
        # El motivo de la lista se guarda como texto en x_motivo_extraordinario (el campo del catálogo); "Otro" usa lo que escribió
        if vals.get('x_motivo_tipo') and vals['x_motivo_tipo'] != 'otro':
            vals['x_motivo_extraordinario'] = dict(MOTIVOS)[vals['x_motivo_tipo']]
        return vals

    # Lo que captura el residente: una vez enviada la requisición ya no cambia (lo autorizado por Costos es lo que se consolida y compra).
    CAMPOS_CAPTURA = {'product_id', 'product_qty', 'product_uom_id', 'x_frente_id', 'x_tipo_requerimiento', 'x_motivo_tipo', 'x_motivo_extraordinario'}

    def _validar_captura_abierta(self, requisiciones):
        if self.env.su:
            return
        cerradas = requisiciones.filtered(lambda r: r.state != 'draft')
        if cerradas:
            raise UserError(_('La requisición %s ya fue enviada: sus insumos no se pueden agregar, quitar ni modificar. '
                              'Si hay que corregirla, debe regresarse a Borrador.') % ', '.join(cerradas.mapped('name')))

    @api.model_create_multi
    def create(self, vals_list):
        self._validar_captura_abierta(self.env['requisition.materials'].browse([v['req_id'] for v in vals_list if v.get('req_id')]))
        return super().create([self._motivo_desde_lista(dict(v)) for v in vals_list])

    def write(self, vals):
        if self.CAMPOS_CAPTURA & set(vals):
            self._validar_captura_abierta(self.mapped('req_id'))
        return super().write(self._motivo_desde_lista(dict(vals)))

    def unlink(self):
        self._validar_captura_abierta(self.mapped('req_id'))
        return super().unlink()

    def action_crear_rfq(self):
        return {'type': 'ir.actions.act_window', 'name': _('Crear Solicitud de Cotización (RFQ)'), 'res_model': 'crear.rfq.consolidada.wizard',
                'view_mode': 'form', 'target': 'new', 'context': {'default_linea_ids': [(6, 0, self.ids)]}}
