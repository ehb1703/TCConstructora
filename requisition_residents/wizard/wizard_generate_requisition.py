# -*- encoding: utf-8 -*-
from odoo import fields, models, api
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
import logging

_logger = logging.getLogger(__name__)

class GenerateRequisitionWizard(models.TransientModel):
    _name = 'generate.requisition.wizard'
    _description = 'Generar requisición semanal'

    def _get_available_domain(self):
        return [('state', '=', 'aprobado')]

    def _get_requisiciones(self):
        return self.env['requisition.residents'].search(self._get_available_domain())

    requisition_ids = fields.Many2many('requisition.residents', 'residents_weelky_rel', 'rweek_id', 'rres_id', 'Requisiciones', 
        default=lambda self: self._get_requisiciones(), required=True, compute='_compute_requisition_ids', store=True, readonly=False)
    fecha = fields.Date(string='Fecha de inicio')

    @api.depends('fecha')
    def _compute_requisition_ids(self):
        for wizard in self:
            domain = wizard.get_requisition_domain()
            wizard.requisition_ids = self.env['requisition.residents'].search(domain)

    def get_requisition_domain(self):
        domain = self._get_available_domain()
        if self.fecha:
            domain = expression.AND([domain, [('finicio', '=', self.fecha)]])
        return domain

    def generate_adeudo(self):
        child = str(self.requisition_ids.ids).replace('[','(').replace(']',')')
        self.env.cr.execute("""SELECT rrl.partner_id, COALESCE(rd.id, 0) prov
            FROM requisition_residents rr JOIN requisition_residents_line rrl ON rr.id = rrl.req_id AND rrl.category not in ('Caja Chica', 'Nómina')
                                          LEFT JOIN requisition_debt rd on rrl.partner_id = rd.partner_id 
            WHERE rr.id in """ + child + " GROUP BY 1, 2 ORDER BY 1")
        proveedores = self.env.cr.dictfetchall()
        for rec in proveedores:
            req_lines = []
            if rec['prov'] != 0:
                proveedor = self.env['requisition.debt'].search([('id','=', rec['prov'])])
            else:
                proveedor = self.env['requisition.debt'].create({'partner_id': rec['partner_id']})

            consulta = ("""SELECT rr.id, rr.name, rr.project_id, rr.finicio, ra.partner_id, 'ACARREO ' category, 
                    STRING_AGG(pt.name->>'es_MX'::text, ',') CONCEPTO, count(*) count, sum(qty) cantidad, sum(ra.amount) precio
                  FROM requisition_residents rr JOIN requisition_acarreos ra ON rr.id = ra.req_id 
                                                JOIN product_product pp ON ra.product_id = pp.id
                                                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                 WHERE rr.id in """ + child + " AND ra.partner_id = " + str(rec['partner_id']) + """
                 GROUP BY 1, 2, 3, 4, 5, 6
                UNION ALL 
                SELECT rr.id, rr.name, rr.project_id, rr.finicio, rd.partner_id, 'DESTAJO' category, STRING_AGG(pt.name->>'es_MX'::text, ','), count(*), sum(rdl.volumen), sum(rdl.amount)
                  from requisition_residents rr JOIN requisition_destajo rd ON rr.id = rd.req_id 
                                                JOIN requisition_destajo_line rdl ON rd.id = rdl.destajo_id 
                                                JOIN product_product pp ON rdl.product_id = pp.id
                                                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                 WHERE rr.id in """ + child + " AND rd.partner_id = " + str(rec['partner_id']) + """
                 GROUP BY 1, 2, 3, 4, 5, 6
                UNION ALL
                SELECT rr.id, rr.name, rr.project_id, rr.finicio, rm.partner_id, 'MAQUINARIA' category, STRING_AGG(rm.MAQUINARIA||' '||coalesce(no_serie, ''), ','), 
                       count(*), sum(rm.total_days), sum(rm.amount)
                  from requisition_residents rr JOIN requisition_maquinaria rm ON rr.id = rm.req_id
                 WHERE rr.id in """ + child + " AND rm.partner_id = " + str(rec['partner_id']) + """
                 GROUP BY 1, 2, 3, 4, 5, 6
                 UNION ALL
                 SELECT rr.id, rr.name, rr.project_id, rr.finicio, rc.partner_id, 'RENTA ' category, STRING_AGG(pt.name->>'es_MX'::text, ',') CONCEPTO, count(*), 0, sum(rc.price)
                  from requisition_residents rr JOIN requisition_campamentos rc ON rr.id = rc.req_id 
                                                JOIN product_product pp ON rc.product_id = pp.id
                                                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                 WHERE rr.id in """ + child + " AND rc.partner_id = " + str(rec['partner_id']) + " GROUP BY 1, 2, 3, 4, 5, 6 ORDER BY 1 ")
            self.env.cr.execute(consulta)
            cargos = self.env.cr.dictfetchall()
            for ca in cargos:
                lines = {'project_id': ca['project_id'], 'fecha': ca['finicio'], 'debit': ca['precio'], 'origen': ca['name'], 'reqres_id': ca['id'], 
                    'concepto': ca['category'] + ' ' + ca['concepto'] + ' ' + str(ca['count']) + ' ' + str(ca['cantidad'])}
                req_lines.append((0, 0, lines))
            
            proveedor.write({'line_ids': req_lines})


    def generate_weekly(self):
        req_lines = []
        name = self.env['ir.sequence'].next_by_code('requisition.weekly.name')

        #Caja chica
        cash = self.env['requisition.residents.line'].search([('req_id','in',self.requisition_ids.ids), ('category','in',['Caja Chica', 'Nómina'])])
        for rec in cash:
            if rec.category == 'Caja Chica':
                concepto = 'Reposición de Caja Chica'
            else:
                concepto = rec.category

            if rec.amount_untaxed != 0:
                lines = {'company_id': rec.req_id.company_id.id, 'project_id': rec.req_id.project_id.id, 'concepto': concepto, 'type_pay': 'EFECTIVO',
                    'partner_id': rec.req_id.employee_id.work_contact_id.id, 'fuerza': 0, 'adeudo': rec.amount_untaxed}
                req_lines.append((0, 0, lines))
            if rec.amount_total != 0:
                lines = {'company_id': rec.req_id.company_id.id, 'project_id': rec.req_id.project_id.id, 'concepto': concepto, 'type_pay': 'FISCAL',
                    'partner_id': rec.req_id.employee_id.work_contact_id.id, 'fuerza': 0, 'adeudo': rec.amount_total}
                req_lines.append((0, 0, lines))
        
        #Distinto a caja chica y nómina
        conceptos = self.env['requisition.debt.line'].search([('reqres_id','in',self.requisition_ids.ids), ('debit','!=',0)])
        for rec in conceptos:
            lines = {'company_id': rec.reqres_id.company_id.id, 'project_id': rec.project_id.id, 'concepto': rec.concepto, 'partner_id': rec.req_id.id, 'fuerza': 0, 
                'type_pay': 'EFECTIVO', 'adeudo': rec.debit, 'debt_id': rec.id}
            req_lines.append((0, 0, lines))
        
        weekly = self.env['requisition.weekly'].create({'name': name, 'finicio': self.fecha, 'state': 'draft', 'line_ids': req_lines, 
            'reqres_ids': self.requisition_ids.ids})
        for rec in self.requisition_ids:
            rec.write({'state': 'req', 'rweekly_id': weekly.id})


    def generate_requisition(self):
        mensaje = ''
        self.ensure_one()
        self.env.cr.execute("""SELECT 'Requisiciones sin aprobar: '||COUNT(*) com, COUNT(*) num FROM requisition_residents rr 
                WHERE rr.state NOT IN ('aprobado', 'req') AND rr.finicio = '""" + str(self.fecha) + """' 
            /*UNION ALL 
            SELECT 'Obras sin requisición: '||COUNT(*), COUNT(*) num 
                FROM project_project pp JOIN project_project_stage pps ON pp.stage_id = pps.id AND pps.name->>'es_MX' NOT IN ('Terminada', 'Cancelada') 
                WHERE NOT EXISTS(SELECT * FROM requisition_residents rr WHERE pp.id = rr.project_id AND rr.finicio = '""" + str(self.fecha) + "')*/")
        pendientes = self.env.cr.dictfetchall()
        for rec in pendientes:
            if rec['num'] != 0:
                mensaje += rec['com'] + '\n'

        if mensaje != '':
            raise ValidationError('No es posible generar la requisición semanal: \n' + mensaje)
        
        if self.requisition_ids:
            self.generate_adeudo()
            week = self.generate_weekly()
        
            success_result = {
                'type': 'ir.actions.act_window',
                'res_model': 'requisition.weekly',
                'views': [[False, 'form']],
                'res_id': week.id,}
            
            return success_result