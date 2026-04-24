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

            consulta = ('''SELECT rr.id, rr.name, rr.project_id, rr.finicio, ra.partner_id, 'ACARREO ' category, type_pay, account_id,
                        STRING_AGG(ra.description||' '||ra.qty||' $'||ra.amount::CHARACTER VARYING, ' || ') CONCEPTO, count(*) count, sum(qty) cantidad, 
                        sum(ra.amount) precio
                    FROM requisition_residents rr JOIN requisition_acarreos ra ON rr.id = ra.req_id 
                    WHERE rr.id in ''' + child + ' AND ra.partner_id = ' + str(rec['partner_id']) + ''' GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
                UNION ALL 
                SELECT rr.id, rr.name, rr.project_id, rr.finicio, rd.partner_id, 'DESTAJO' category, type_pay, account_id,
                        STRING_AGG(pt.name->>'es_MX'::text||' '||rdl.volumen||' $'||rdl.amount, ' || '), count(*), sum(rdl.volumen), sum(rdl.amount)
                    FROM requisition_residents rr JOIN requisition_destajo rd ON rr.id = rd.req_id 
                                                JOIN requisition_destajo_line rdl ON rd.id = rdl.destajo_id 
                                                JOIN product_product pp ON rdl.product_id = pp.id
                                                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                    WHERE rr.id in ''' + child + ' AND rd.partner_id = ' + str(rec['partner_id']) + ''' GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
                UNION ALL
                SELECT t1.id, t1.name, t1.project_id, t1.finicio, t1.partner_id, t1.category, t1.TYPE_PAY, t1.ACCOUNT_ID, 
                        STRING_AGG(t1.concepto, ' || '), sum(t1.num), sum(dias), sum(total)
                    FROM (SELECT rr.id, rr.name, rr.project_id, rr.finicio, rm.partner_id, 'MAQUINARIA' category, type_pay, account_id,
                            STRING_AGG(rm.MAQUINARIA||' '||coalesce(no_serie, '')||' $'||rm.amount::CHARACTER VARYING, ' || ') concepto, count(*) num, sum(rm.total_days) dias, sum(rm.amount) total
                        FROM requisition_residents rr JOIN requisition_maquinaria rm ON rr.id = rm.req_id
                        WHERE rr.id in ''' + child + ' AND rm.partner_id = ' + str(rec['partner_id']) + ''' GROUP BY 1, 2, 3, 4, 5, 6, 7, 8  
                        UNION ALL
                        SELECT rr.id, rr.name, rr.project_id, rr.finicio, rm.partner_id, 'MAQUINARIA' category, type_pay, account_id,
                                STRING_AGG(rmf.FECHA||' '||rmf.ORIGEN||' '||rmf.DESTINO||' $'||rmf.amount::CHARACTER VARYING, ' || '), count(*), 0, sum(rmf.amount)
                            FROM requisition_residents rr JOIN requisition_maquinaria rm ON rr.id = rm.req_id
                                                        JOIN requisition_maquinaria_flete rmf ON rm.id = rmf.maquinaria_id 
                            WHERE rr.id in ''' + child + ' AND rm.partner_id = ' + str(rec['partner_id']) + ''' GROUP BY 1, 2, 3, 4, 5, 6, 7, 8                    
                        UNION ALL
                        SELECT rr.id, rr.name, rr.project_id, rr.finicio, rm.partner_id, 'MAQUINARIA' category, type_pay, account_id,
                                STRING_AGG(rp.name||' $'||rmn.salary::CHARACTER VARYING, ' || '), count(*), 0, sum(rmn.salary)
                            FROM requisition_residents rr JOIN requisition_maquinaria rm ON rr.id = rm.req_id
                                                            join requisition_maquinaria_nomina rmn on rm.id = rmn.maquinaria_id 
                                                            join res_partner rp on rmn.partner_id = rp.id
                            WHERE rr.id in ''' + child + ' AND rm.partner_id = ' + str(rec['partner_id']) + ''' GROUP BY 1, 2, 3, 4, 5, 6, 7, 8) as t1 
                    GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
                UNION ALL
                SELECT rr.id, rr.name, rr.project_id, rr.finicio, rc.partner_id, 'RENTA ' category, type_pay, account_id,
                        STRING_AGG(pt.name->>'es_MX'::text||' $'||rc.PRICE::CHARACTER VARYING, ' || ') CONCEPTO, count(*), 0, sum(rc.price)
                    FROM requisition_residents rr JOIN requisition_campamentos rc ON rr.id = rc.req_id 
                                                JOIN product_product pp ON rc.product_id = pp.id
                                                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                    WHERE rr.id in ''' + child + ' AND rc.partner_id = ' + str(rec['partner_id']) + ''' GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
                UNION ALL
                SELECT rr.id, rr.name, rr.project_id, rr.finicio, rf.partner_id, 'COMBUSTIBLE ' category, type_pay, account_id,
                        STRING_AGG(rfl.EQUIPO||' $'||rfl.AMOUNT::CHARACTER VARYING, ' || ') CONCEPTO, count(*), 0, sum(rfl.amount)
                    FROM requisition_residents rr JOIN requisition_fuel rf ON rr.id = rf.req_id
                                                JOIN requisition_fuel_line rfl ON rf.id = rfl.fuel_id 
                    WHERE rr.id in ''' + child + ' AND rf.partner_id = ' + str(rec['partner_id']) + ''' GROUP BY 1, 2, 3, 4, 5, 6, 7, 8 
                UNION ALL
                SELECT rr.id, rr.name, rr.project_id, rr.finicio, ro.partner_id, 'OTROS GASTOS ' category, ro.type_pay, ro.account_id,
                        STRING_AGG(pt.name->>'es_MX'::text||' $'||ro.AMOUNT::CHARACTER VARYING, ' || ') CONCEPTO, count(*), 0, sum(ro.amount)
                    FROM requisition_residents rr JOIN requisition_other ro ON rr.id = ro.req_id
                                                JOIN product_product pp ON ro.product_id = pp.id
                                                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                    WHERE rr.id in ''' + child + ' AND ro.partner_id = ' + str(rec['partner_id']) + " GROUP BY 1, 2, 3, 4, 5, 6, 7, 8 ORDER BY 1 ")
            self.env.cr.execute(consulta)
            cargos = self.env.cr.dictfetchall()
            for ca in cargos:
                lines = {'project_id': ca['project_id'], 'fecha': ca['finicio'], 'debit': ca['precio'], 'origen': ca['name'], 'reqres_id': ca['id'], 
                    'type_pay': ca['type_pay'], 'concepto': ca['category'] + ' ' + ca['concepto'] + ' ' + str(ca['count']) + ' ' + str(ca['cantidad']),
                    'account_id': ca['account_id']}
                req_lines.append((0, 0, lines))
            
            proveedor.write({'line_ids': req_lines})


    def generate_weekly(self):
        req_lines = []
        child = str(self.requisition_ids.ids).replace('[','(').replace(']',')')
        name = self.env['ir.sequence'].next_by_code('requisition.weekly.name')

        #Caja chica
        cash = self.env['requisition.residents.line'].search([('req_id','in',self.requisition_ids.ids), ('category','in',['Caja Chica', 'Nómina'])])
        for rec in cash:
            if rec.category == 'Caja Chica':
                if rec.req_id.employee_id.facil_tarjeta:
                    destino = rec.req_id.employee_id.facil_tarjeta
                else:
                    destino = self.env['res.partner.bank'].search([('bank_name','=','TARJETA FACIL')], limit=1)

                #if destino.type_pay == 'estrategia': --Para pruebas
                if not destino or destino.type_pay == 'estrategia':
                    tipo = 'EFECTIVO'
                else:
                    tipo = destino.type_pay.upper()

                total = rec.amount_untaxed + rec.amount_total
                lines = {'company_id':rec.req_id.company_id.id, 'project_id':rec.req_id.project_id.id, 'concepto':'Reposición de Caja Chica', 'type_pay':tipo, 
                    'partner_id':rec.req_id.employee_id.work_contact_id.id, 'fuerza':0, 'adeudo':total, 'account_dest':destino.id}
                req_lines.append((0, 0, lines))
            else:
                concepto = rec.category
                if rec.amount_untaxed != 0:
                    lines = {'company_id':rec.req_id.company_id.id, 'project_id':rec.req_id.project_id.id, 'concepto':concepto, 'type_pay':'EFECTIVO',
                        'partner_id':rec.req_id.employee_id.work_contact_id.id, 'fuerza':0, 'adeudo':rec.amount_untaxed}
                    req_lines.append((0, 0, lines))
                if rec.amount_total != 0:
                    lines = {'company_id':rec.req_id.company_id.id, 'project_id':rec.req_id.project_id.id, 'concepto':concepto, 'type_pay':'FISCAL',
                        'partner_id':rec.req_id.employee_id.work_contact_id.id, 'fuerza':0, 'adeudo':rec.amount_total}
                    req_lines.append((0, 0, lines))

        #Adeudo anterior
        consulta = ('''SELECT t1.project_id, rr.company_id, t1.concepto, rd.partner_id, rd.id supplier_id, t1.id, t1.type_pay, rw.name, 
                (t1.debit - t1.credit) debit 
            FROM (SELECT project_id, req_id, concepto, reqres_id, MIN(type_pay) type_pay, MIN(id) id, SUM(debit) debit, SUM(credit) credit 
                    FROM requisition_debt_line rdl 
                    WHERE req_id IS NOT NULL AND reqres_id NOT IN ''' + child + ''' GROUP BY 1, 2, 3, 4) as t1 
                JOIN requisition_residents rr ON t1.reqres_id = rr.id JOIN requisition_debt rd on t1.req_id = rd.id
                JOIN requisition_weekly rw ON rr.rweekly_id = rw.id
            WHERE (t1.credit - t1.debit) != 0''')
        self.env.cr.execute(consulta)
        cargos = self.env.cr.dictfetchall()
        for rec in cargos:
            lines = {'company_id': rec['company_id'], 'project_id': rec['project_id'], 'concepto': rec['concepto'], 'origen': rec['name'],
                'partner_id': rec['partner_id'], 'supplier_id': rec['supplier_id'], 'fuerza': 0, 'type_pay': rec['type_pay'], 'adeudo': rec['debit'], 
                'debt_id': rec['id']}
            req_lines.append((0, 0, lines))
        
        #Distinto a caja chica y nómina
        conceptos = self.env['requisition.debt.line'].search([('reqres_id','in',self.requisition_ids.ids), ('debit','!=',0)])
        for rec in conceptos:
            lines = {'company_id': rec.reqres_id.company_id.id, 'project_id': rec.project_id.id, 'concepto': rec.concepto, 
                'partner_id': rec.req_id.partner_id.id, 'supplier_id': rec.req_id.id, 'fuerza': 0, 'type_pay': rec.type_pay, 'adeudo': rec.debit, 
                'debt_id': rec.id}
            req_lines.append((0, 0, lines))
        
        weekly = self.env['requisition.weekly'].create({'name': name, 'finicio': self.fecha, 'state': 'draft', 'line_ids': req_lines, 
            'reqres_ids': self.requisition_ids.ids})
        for rec in self.requisition_ids:
            rec.write({'state': 'req', 'rweekly_id': weekly.id})
        return weekly


    def generate_requisition(self):
        mensaje = ''
        self.ensure_one()
        self.env.cr.execute("""SELECT 'Requisiciones sin aprobar: '||COUNT(*) com, COUNT(*) num FROM requisition_residents rr 
                WHERE rr.state NOT IN ('aprobado', 'req') AND rr.finicio = '""" + str(self.fecha) + """' 
            /*UNION ALL 
            SELECT 'Obras sin requisición: '||COUNT(*), COUNT(*) num 
                FROM project_project pp JOIN project_project_stage pps ON pp.stage_id = pps.id 
                                                                    AND pps.name->>'es_MX' NOT IN ('Terminada', 'Cancelada', 'Detenida') 
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
