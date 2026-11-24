# -*- coding: utf-8 -*-
from odoo import fields, models

SIN_DESTAJISTAS = [('tipo_personal', '!=', 'destajista')]

# Los destajistas no se eligen en Asistencias ni en Nómina: se consultan solo en el módulo Destajistas.
# Se conservan los dominios que ya pone hr_extra (finiquito y empresa) y se agrega la condición de tipo de personal.


class HrAttendanceSinDestajistas(models.Model):
    _inherit = 'hr.attendance'

    employee_id = fields.Many2one(domain=[('finiquito', '=', False)] + SIN_DESTAJISTAS)


class HrContractSinDestajistas(models.Model):
    _inherit = 'hr.contract'

    employee_id = fields.Many2one(domain="[('finiquito', '=', False), '|', ('company_id', '=', False), ('company_id', '=', company_id), "
                                         "('tipo_personal', '!=', 'destajista')]")


class HrPayslipSinDestajistas(models.Model):
    _inherit = 'hr.payslip'

    employee_id = fields.Many2one(domain="[('finiquito', '=', False), '|', ('company_id', '=', False), ('company_id', '=', company_id), "
                                         "'|', ('active', '=', True), ('active', '=', False), ('tipo_personal', '!=', 'destajista')]")


class RequisitionDestajoConsulta(models.Model):
    _inherit = 'requisition.destajo'

    # Datos de la requisición para la consulta de pagos en el módulo Destajistas (los campos relacionados se leen con sudo,
    # así el grupo Destajistas no necesita acceso a las requisiciones)
    destajo_requisicion = fields.Char(string='Requisición', related='req_id.name')
    destajo_obra = fields.Char(string='Obra', related='req_id.project_id.name')
    destajo_periodo_inicio = fields.Date(string='Periodo inicial', related='req_id.finicio')
    destajo_periodo_fin = fields.Date(string='Periodo final', related='req_id.ffinal')
    destajo_tipo = fields.Char(string='Tipo de destajo', related='destajo_id.nombre')

