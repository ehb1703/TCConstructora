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
                values['name'] = '%s - [%s] %s' % (values['name'], self.product_id.default_code, self.product_id.name) if self.product_id.default_code else '%s - %s' % (values['name'], self.product_id.name)
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
