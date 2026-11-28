# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError

GRUPO_ADMIN = 'catalogo_tc.group_admin_catalogo'
FUENTE_UNIFICACION = 'UNIFICACIÓN DE DUPLICADOS'


class CatalogoUnificarWizard(models.TransientModel):
    """Une productos que son el mismo insumo (p. ej. AGUA [MA0001] de una carga anterior y AGUA con Clave TC): se conserva uno; los demás
    dejan su referencia y sus equivalencias apuntando al que se conserva y se archivan. No se borra nada: compras, movimientos y
    presupuestos anteriores conservan su producto (archivado) para la historia."""
    _name = 'catalogo.unificar.wizard'
    _description = 'Unificar insumos duplicados'

    producto_ids = fields.Many2many('product.template', string='Productos a unificar')
    conservar_id = fields.Many2one('product.template', string='Se conserva', domain="[('id', 'in', producto_ids)]",
        help='El insumo que queda. De preferencia el que ya tiene Clave TC.')
    resumen = fields.Html(string='Qué pasará', compute='_compute_resumen', sanitize=False)

    @api.model
    def default_get(self, campos):
        res = super().default_get(campos)
        ids = self.env.context.get('active_ids') if self.env.context.get('active_model') == 'product.template' else []
        productos = self.env['product.template'].browse(ids or (res.get('producto_ids') and res['producto_ids'][0][2]) or [])
        if productos:
            res['producto_ids'] = [(6, 0, productos.ids)]
            res['conservar_id'] = (productos.filtered('clave_insumo') or productos).sorted('id')[:1].id
        return res

    @api.depends('producto_ids', 'conservar_id')
    def _compute_resumen(self):
        importador = self.env['catalogo.importador']
        for wiz in self:
            filas = Markup('').join(
                Markup('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>') % (
                    p.display_name, p.uom_id.name or '', _('Se conserva') if p == wiz.conservar_id else _('Se archiva'),
                    ', '.join(importador._referencias(p)) or '-')
                for p in wiz.producto_ids.sorted('id'))
            wiz.resumen = Markup('<table class="table table-sm"><thead><tr><th>%s</th><th>%s</th><th>%s</th><th>%s</th></tr></thead>'
                                 '<tbody>%s</tbody></table>') % (_('Producto'), _('Unidad'), _('Resultado'), _('Dónde se usa'), filas)

    def action_unificar(self):
        self.ensure_one()
        if not self.env.user.has_group(GRUPO_ADMIN):
            raise UserError(_('Solo el Administrador del Catálogo puede unificar insumos.'))
        conservar, otros = self.conservar_id, self.producto_ids - self.conservar_id
        if not conservar or conservar not in self.producto_ids or not otros:
            raise UserError(_('Seleccione al menos dos productos y elija cuál se conserva.'))
        motor = self.env['catalogo.motor']
        unidades = {motor.unidad_canonica(p.uom_id.name) for p in self.producto_ids}
        if len(unidades) > 1:
            raise UserError(_('No se unifican insumos con distinta unidad (%s): no son el mismo insumo o primero debe corregirse la unidad.')
                            % ', '.join(sorted(unidades)))
        Eq = self.env['catalogo.equivalencia'].sudo().with_context(active_test=False)
        importador = self.env['catalogo.importador']
        lineas = []
        for otro in otros:
            usos = importador._referencias(otro)
            otro.sudo().with_context(active_test=False).equivalencia_ids.write({'product_tmpl_id': conservar.id})
            if otro.default_code and not Eq.search_count([('fuente_norm', '=', motor.normalizar(FUENTE_UNIFICACION)),
                                                          ('codigo_norm', '=', motor.normalizar(otro.default_code))]):
                Eq.create({'fuente': FUENTE_UNIFICACION, 'codigo_externo': otro.default_code, 'descripcion_externa': otro.name,
                           'unidad_externa': otro.uom_id.name, 'product_tmpl_id': conservar.id})
            otro.sudo().write({'active': False})
            lineas.append(Markup('<li>%s%s</li>') % (otro.display_name, (' — ' + _('su historial queda en el producto archivado: ') + ', '.join(usos)) if usos else ''))
        # nota interna (no envía correos: no exige que el administrador tenga correo configurado)
        conservar._message_log(body=Markup('<p>%s</p><ul>%s</ul>') % (_('Se unificaron en este insumo (archivados):'), Markup('').join(lineas)))
        return {'type': 'ir.actions.act_window', 'res_model': 'product.template', 'res_id': conservar.id, 'view_mode': 'form', 'target': 'current'}
