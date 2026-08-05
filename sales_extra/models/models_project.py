# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

class saleOrderInherit(models.Model):
    _inherit = 'sale.order'

    anticipo_porcentaje = fields.Float(string='% Anticipo')
    anticipo_importe = fields.Monetary(string='Importe Anticipo (IVA incluido)')
    tiene_anticipo = fields.Boolean(string='Tiene Anticipo')
    factura_anticipo_generada = fields.Boolean(string='Factura Anticipo Generada')
    has_obra = fields.Boolean(string='Tiene obra vinculada', compute='_compute_has_obra')

    def _obras_vinculadas(self):
        # Obra(s) generada(s) por esta OV: por reinvoiced_sale_order_id o por el project_id de la orden.
        self.ensure_one()
        if not isinstance(self.id, int):
            return self.env['project.project']
        domain = [('reinvoiced_sale_order_id', '=', self.id)]
        if self.project_id:
            domain = ['|', ('id', '=', self.project_id.id)] + domain
        return self.env['project.project'].search(domain)

    @api.depends('project_id', 'state')
    def _compute_has_obra(self):
        for order in self:
            order.has_obra = bool(order._obras_vinculadas())

    def action_eliminar_obra(self):
        # Elimina la(s) obra(s) creada(s) por esta OV. Solo con la OV cancelada, para deshacer
        # una obra generada por error (al cancelar la OV la obra no se borra sola).
        self.ensure_one()
        if self.state != 'cancel':
            raise UserError(_('Solo se puede eliminar la obra cuando la orden de venta está cancelada.'))
        obras = self._obras_vinculadas()
        if not obras:
            raise UserError(_('No hay ninguna obra vinculada a esta orden de venta.'))
        nombres = ', '.join(obras.mapped('name'))
        # Desligar líneas y borrar tareas antes de la obra para evitar referencias colgadas.
        self.order_line.write({'project_id': False, 'task_id': False})
        self.env['project.task'].search([('project_id', 'in', obras.ids)]).unlink()
        cuentas = obras.mapped('account_id')
        obras.unlink()
        # Al borrar la obra, Odoo borra su cuenta analítica en cascada. Solo tocar las que
        # SIGAN existiendo (p.ej. compartidas) y estén vacías; usar .exists() evita el
        # MissingError sobre una cuenta ya eliminada en cascada.
        for cuenta in cuentas.exists():
            if not self.env['account.analytic.line'].search_count([('account_id', '=', cuenta.id)]) \
                    and not self.env['project.project'].search_count([('account_id', '=', cuenta.id)]):
                cuenta.unlink()
        self.message_post(body=_('Obra(s) eliminada(s) desde la OV cancelada: %s') % nombres)
        return True

    def action_confirm(self):
        # Sobrescribir la confirmación para mostrar wizard de anticipo si la orden tiene anticipo configurado. Si viene del wizard, no mostrar wizard otra vez
        if self._context.get('skip_advance_wizard'):
            return super().action_confirm()
        
        for order in self:
            # Si tiene anticipo y no se ha generado la factura, mostrar wizard
            if order.tiene_anticipo and not order.factura_anticipo_generada:
                return {
                    'name': _('¿Desea generar la factura del anticipo ahora?'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'sale.advance.invoice.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {'active_id': order.id, 'active_model': 'sale.order',}}
        
        # Si no tiene anticipo, confirmar normalmente
        return super().action_confirm()


    def action_create_advance_invoice(self):
        # Acción manual para crear factura de anticipo desde la orden de venta. Disponible después de confirmar la orden sin generar factura.
        self.ensure_one()
        
        if not self.tiene_anticipo:
            raise UserError(_('Esta orden de venta no tiene anticipo configurado.'))
        
        if self.factura_anticipo_generada:
            raise UserError(_('Ya se ha generado la factura de anticipo para esta orden.'))
        
        # Abrir wizard para generar factura
        return {
            'name': _('Generar Factura de Anticipo'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.advance.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id, 'active_model': 'sale.order', 'skip_confirmation': True,}}


class saleOrderLineInherit(models.Model):
    _inherit = 'sale.order.line'
    
    # Modificación de la función original
    def _timesheet_create_project(self):        
        self.ensure_one()
        values = self._timesheet_create_project_prepare_values()
        project_template = self.product_id.project_template_id
        if project_template:
            values['name'] = '%s - %s' % (values['name'], project_template.name)
            project = project_template.copy(values)
            project.tasks.write({'sale_line_id': self.id, 'partner_id': self.order_id.partner_id.id,})
            project.tasks.filtered('parent_id').write({'sale_line_id': self.id, 'sale_order_id': self.order_id.id,})
        else:
            project_only_sol_count = self.env['sale.order.line'].search_count([('order_id', '=', self.order_id.id), 
                ('product_id.service_tracking', 'in', ['project_only', 'task_in_project']),])
            if project_only_sol_count == 1:
                values['name'] = '%s - [%s] %s' % (values['name'], self.product_id.default_code, 
                    self.product_id.name) if self.product_id.default_code else '%s - %s' % (values['name'], self.product_id.name)
            
            values.update(self._timesheet_create_project_account_vals(self.order_id.project_id))
            if self.order_id.opportunity_id:
                opp = self.order_id.opportunity_id
                no_lic = opp.no_licitacion or ''
                
                vals_crm = {
                    'lead_id': opp.id,
                    'type_id': opp.tipo_obra_id.id if opp.tipo_obra_id else False,
                    'num_contrato': opp.contrato_documento_name,
                    'dependencia': opp.partner_emisor_id.name if opp.partner_emisor_id else False,
                    # Campos de cabecera "Orden de Trabajo" - usando campos existentes
                    'licitacion': opp.no_licitacion,  # Asignación/No. Proceso
                    'orden_trabajo': no_lic[-12:] if len(no_lic) >= 12 else no_lic,
                    'proj_fecha_adjudicacion': opp.fallo_fecha_adjudicacion,
                    'partner_id': opp.partner_emisor_id.id if opp.partner_emisor_id else False,  # Dependencia
                    'description': opp.desc_licitacion,  # Descripción
                    'company_id': opp.company_id.id if opp.company_id else False,  # Ejecutor
                    'date_start': opp.bases_fecha_inicio_trabajos,  # Fecha de inicio
                    'date': opp.bases_fecha_terminacion_trabajos,  # Fecha de término
                    'proj_dias': opp.bases_plazo_ejecucion,
                    'authorized_budget': opp.importe_contratado,  # Importe contratado
                    'proj_anticipo_porcentaje': opp.bases_anticipo_porcentaje,
                    'proj_importe_anticipo': opp.importe_anticipo,
                    # Campos de pestaña "Datos de la obra"
                    'modalidad_contratacion_id': opp.bases_modalidad_contrato_id.id if opp.bases_modalidad_contrato_id else False,
                    'proj_fecha_apertura': opp.fecha_apertura,
                    'proj_rupc_siop': opp.rupc_siop,
                    'proj_es_siop': opp.es_siop,
                    'proj_sancion_atraso': opp.bases_sancion_atraso,
                    'proj_ret_5_millar': opp.bases_ret_5_millar,
                    'proj_ret_2_millar': opp.bases_ret_2_millar,
                }
                values.update(vals_crm)

                # --- T0101: Logica de BLOQUE ---
                if opp.bloque_id:
                    proyecto_bloque = self.env['project.project'].search([('bloque', '=', opp.bloque_id.name)], limit=1)
                    if proyecto_bloque:
                        # La obra del bloque ya existe: vincular esta orden y terminar sin crear duplicado
                        if not proyecto_bloque.type_ids:
                            proyecto_bloque.type_ids = self.env['project.task.type'].create([{'name': name, 'fold': fold, 'sequence': sequence,} for name, fold, sequence in [
                                (_('To Do'), False, 5), (_('In Progress'), False, 10), (_('Done'), False, 15), (_('Cancelled'), True, 20),]])
                        self.write({'project_id': proyecto_bloque.id})
                        proyecto_bloque.reinvoiced_sale_order_id = self.order_id
                        return proyecto_bloque
                    # No existe: crear la obra con el NOMBRE DEL BLOQUE
                    values['name'] = opp.bloque_id.name
                    values['bloque'] = opp.bloque_id.name

            project = self.env['project.project'].create(values)
            project.cargar_docs()

        if not project.type_ids:
            project.type_ids = self.env['project.task.type'].create([{'name': name, 'fold': fold, 'sequence': sequence,} for name, fold, sequence in [
                (_('To Do'), False, 5),
                (_('In Progress'), False, 10),
                (_('Done'), False, 15),
                (_('Cancelled'), True, 20),]])

        self.write({'project_id': project.id})
        project.reinvoiced_sale_order_id = self.order_id
        return project
