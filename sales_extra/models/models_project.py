# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import base64
import io
import openpyxl
import logging

_logger = logging.getLogger(__name__)

class saleOrderLineInherit(models.Model):
    _inherit = 'sale.order'

    concept_ids = fields.One2many('sale.concept.line', 'sale_id', string='Conceptos de trabajo')

    def action_load_price(self):
        docto = self.env['documents.document'].search([('res_model','=','crm.lead'), ('res_id','=',self.opportunity_id.id), '|', ('name','ilike','E02'), 
            ('name','ilike','Economico 2')])
        if not docto:
            raise ValidationError('El documento E02 no se encuentra cargado, favor de agregar el precio unitario manualmente.')

        attachment = docto.attachment_id
        decoded_data = base64.b64decode(attachment.datas)
        workbook = openpyxl.load_workbook(filename=io.BytesIO(decoded_data), data_only=True)
        sheet = workbook.active
        c = 0
        d = 0
        if not self.concept_ids:
            registros = []
            for row in sheet.iter_rows(values_only=True):
                if row[0] == 'CLAVE':
                    for cell in row:
                        if cell in ('PRECIO UNITARIO', 'PRECIO UNITARIO ($) PROPUESTO'):
                            d = c
                        else:
                            c += 1
                concepto = self.env['crm.concept.line'].search([('lead_id','=',self.opportunity_id.id), ('concept_id.default_code','=',row[0])])
                if concepto:
                    registro = {'default_code': row[0], 'price_unit': row[d]}
                    registros.append((0, 0, registro))
            self.write({'concept_ids': registros})

        self.env.cr.execute('''SELECT NUM, MAX(ID) ID, MAX(PRICE_UNIT) PRICE
            FROM (SELECT ROW_NUMBER() OVER (ORDER BY id) NUM, 0 ID, PRICE_UNIT FROM sale_concept_line scl WHERE SALE_ID = ''' + str(self.id) + ''' UNION ALL
                SELECT ROW_NUMBER() OVER (ORDER BY id) NUM, ID, 0 FROM sale_order_line ccl WHERE order_id = ''' + str(self.id) + ''') as t1
            GROUP BY 1 ORDER BY 1''')
        lines = self.env.cr.dictfetchall()        
        for rec in lines:
            line = self.env['sale.order.line'].search([('id','=',rec['id'])])
            line.write({'price_unit': rec['price']})


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


class saleConceptLine(models.Model):
    _name = 'sale.concept.line'
    _description = 'Conceptos de trabajo'
    
    sale_id = fields.Many2one(comodel_name='sale.order', string='Orden de venta', readonly=True)
    default_code = fields.Char(string='Concepto cargado')
    price_unit = fields.Float(string='Precio unitario')
