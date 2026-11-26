# -*- coding: utf-8 -*-
from collections import OrderedDict

from markupsafe import Markup
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CrearRfqConsolidadaWizard(models.TransientModel):
    """Especificación, paso 3: el comprador selecciona requisiciones autorizadas de distintos frentes del mismo Proyecto Global
    y genera una Solicitud de Cotización por proveedor con las cantidades de todos los frentes. Cada línea de la cotización es
    un insumo de un frente, con la cuenta analítica de ese frente (paso 5: imputación por frente)."""
    _name = 'crear.rfq.consolidada.wizard'
    _description = 'Crear Solicitud de Cotización consolidada'

    linea_ids = fields.Many2many('requisition.materials.line', string='Insumos a cotizar')
    proveedor_ids = fields.Many2many('res.partner', string='Proveedores', domain=[('is_supplier', '=', True)],
        help='Se genera una Solicitud de Cotización por proveedor con todos los insumos seleccionados. Sin proveedor se genera una '
             'para que Compras lo asigne.')
    resumen = fields.Html(string='Resumen', compute='_compute_resumen', sanitize=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        lineas = self.env['requisition.materials.line'].browse(res.get('linea_ids') and res['linea_ids'][0][2] or [])
        if 'proveedor_ids' in fields_list and lineas:
            res['proveedor_ids'] = [(6, 0, lineas.mapped('supplier_ids').ids)]
        return res

    @api.depends('linea_ids')
    def _compute_resumen(self):
        for wiz in self:
            filas = Markup('').join(Markup('<tr><td>%s</td><td>%s</td><td class="text-end">%s %s</td></tr>') % (
                g['producto'].display_name, g['frente'].display_name, g['cantidad'], g['producto'].uom_po_id.name or '')
                for g in wiz._agrupar().values())
            wiz.resumen = Markup('<p><b>%s</b> · %s requisición(es)</p><table class="table table-sm"><thead><tr><th>%s</th><th>%s</th>'
                                 '<th class="text-end">%s</th></tr></thead><tbody>%s</tbody></table>') % (
                ', '.join(wiz.linea_ids.mapped('x_proyecto_id.display_name')) or '-', len(wiz.linea_ids.mapped('req_id')),
                _('Insumo'), _('Frente / Contrato'), _('Cantidad'), filas)

    def _agrupar(self):
        """Una línea de cotización por insumo, frente y tipo de requerimiento, con la suma de lo solicitado."""
        grupos = OrderedDict()
        for linea in self.linea_ids.sorted(lambda l: (l.product_id.id, l.x_frente_id.id, l.id)):
            llave = (linea.product_id.id, linea.x_frente_id.id, linea.x_tipo_requerimiento)
            g = grupos.setdefault(llave, {'producto': linea.product_id, 'frente': linea.x_frente_id, 'tipo': linea.x_tipo_requerimiento,
                                          'cantidad': 0.0, 'lineas': self.env['requisition.materials.line'], 'motivos': []})
            g['cantidad'] += linea.product_qty
            g['lineas'] |= linea
            if linea.x_motivo_extraordinario and linea.x_motivo_extraordinario not in g['motivos']:
                g['motivos'].append(linea.x_motivo_extraordinario)
        return grupos

    def _validar(self):
        lineas = self.linea_ids
        if not lineas:
            raise UserError(_('Seleccione los insumos a cotizar.'))
        no_pendientes = lineas.filtered(lambda l: not l.x_pendiente_cotizar)
        if no_pendientes:
            raise UserError(_('Solo se cotizan insumos de requisiciones Enviadas a Compras que aún no tienen cotización: %s.')
                            % ', '.join(sorted(set(no_pendientes.mapped('req_id.name')))))
        if len(lineas.mapped('x_proyecto_id')) != 1:
            raise UserError(_('La consolidación se hace por Proyecto Global: seleccione insumos de un solo proyecto.'))
        sin_frente = lineas.filtered(lambda l: not l.x_frente_id)
        if sin_frente:
            raise UserError(_('Asigne el Bloque / Frente / Contrato a: %s.') % ', '.join(sin_frente.mapped('product_id.display_name')))

    def _distribucion(self, obra, frente):
        # Cuenta Analítica Destino: el frente. Si el frente es de otro plan que la obra, la distribución lleva ambas cuentas
        # (la obra es obligatoria en compras por la regla de N1 de T0110).
        cuenta_obra = obra.account_id
        if not cuenta_obra or frente == cuenta_obra or frente.root_plan_id == cuenta_obra.root_plan_id:
            return {str(frente.id): 100.0}
        return {'%s,%s' % (cuenta_obra.id, frente.id): 100.0}

    def action_generar(self):
        self.ensure_one()
        self._validar()
        obra = self.linea_ids.mapped('x_proyecto_id')
        requisiciones = self.linea_ids.mapped('req_id')
        empresa = self.env.user.company_id
        grupos = self._agrupar()
        ordenes = self.env['purchase.order']
        for proveedor in (self.proveedor_ids or [self.env['res.partner']]):
            fpos = self.env['account.fiscal.position'].with_company(empresa)._get_fiscal_position(proveedor) if proveedor \
                else self.env['account.fiscal.position']
            lineas_oc = []
            for g in grupos.values():
                impuestos = g['producto'].supplier_taxes_id._filter_taxes_by_company(empresa)
                lineas_oc.append((0, 0, {
                    'product_id': g['producto'].id, 'name': g['producto'].display_name, 'product_qty': g['cantidad'],
                    'product_uom': g['producto'].uom_po_id.id or g['producto'].uom_id.id, 'price_unit': 0.0, 'taxes_id': fpos.map_tax(impuestos),
                    'x_frente_id': g['frente'].id, 'x_tipo_requerimiento': g['tipo'],
                    'x_motivo_extraordinario': '\n'.join(g['motivos']) or False,
                    'analytic_distribution': self._distribucion(obra, g['frente'])}))
            orden = self.env['purchase.order'].create({
                'partner_id': proveedor.id, 'company_id': empresa.id, 'currency_id': empresa.currency_id.id, 'user_id': self.env.uid,
                'origin': _('Consolidado - %s') % ', '.join(requisiciones.mapped('name')), 'type_purchase': 'mat',
                'project_id': obra.id, 'materials_id': requisiciones.id if len(requisiciones) == 1 else False, 'order_line': lineas_oc})
            for linea_oc, g in zip(orden.order_line, grupos.values()):
                linea_oc.sudo().x_requisicion_line_ids = [(6, 0, g['lineas'].ids)]
            ordenes |= orden
        for req in requisiciones.sudo():
            # nota automática en la requisición; el comprador solo tiene lectura de las requisiciones
            req._post_html(_('Compras consolidó sus insumos en: ') + ', '.join(ordenes.mapped('name')))
        return {'type': 'ir.actions.act_window', 'name': _('Solicitudes de cotización consolidadas'), 'res_model': 'purchase.order',
                'view_mode': 'list,form', 'domain': [('id', 'in', ordenes.ids)]}
