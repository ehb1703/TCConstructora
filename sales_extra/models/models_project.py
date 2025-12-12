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
                vals = {'licitacion': self.order_id.opportunity_id.no_licitacion, 'type_id': self.order_id.opportunity_id.tipo_obra_id.id,
                    'num_contrato': self.order_id.opportunity_id.contrato_documento_name, 'dependencia': self.order_id.opportunity_id.partner_emisor_id.name}
                values.update(vals)
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
