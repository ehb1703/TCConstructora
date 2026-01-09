# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

class HrEmployeeObra(models.Model):
    _name = 'hr.employee.obra'
    _description = 'Obra asignada a empleado'
    _order = 'employee_id, id'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    project_id = fields.Many2one('project.project', string='Nombre de la obra', required=True)
    etapa_id = fields.Many2one('project.project.stage', string='Etapa', related='project_id.stage_id', readonly=True, store=True)
    fecha_inicio = fields.Date(string='Fecha inicio', related='project_id.fecha_inicio_obra', readonly=True, store=True)
    fecha_fin = fields.Date(string='Fecha fin', related='project_id.fecha_fin_obra', readonly=True, store=True)

class hrEmployeeInherit(models.Model):
    _inherit = 'hr.employee'

    infonavit = fields.Char(string='Infonavit')
    fonacot = fields.Char(string='Fonacot')
    obra_ids = fields.One2many('hr.employee.obra', 'employee_id', string='Obras asignadas')
    director_ids = fields.Many2many('hr.employee', 'hr_employee_director_rel', 'employee_id', 'director_id', string='Director/Gerente',
        domain="[('job_id.name', 'ilike', 'Director')]")

    @api.onchange('work_contact_id')
    def onchange_name(self):
        if self.work_contact_id:
            self.name = self.work_contact_id.name

class hrContractInherit(models.Model):
    _inherit = 'hr.contract'

    beneficiario_ids = fields.One2many('hr.contract.beneficiario', 'contract_id', string='Beneficiarios')
    total_porcentaje = fields.Integer(string='Total', compute='_compute_total_porcentaje', store=True)
    contract_type_name = fields.Char(string='Tipo de contrato nombre', related='contract_type_id.name', store=False)
    project_id = fields.Many2one('project.project', string='Obra')
    l10n_mx_schedule_pay_temp = fields.Selection(selection=[('daily', 'Diario'), ('weekly', 'Semanal'), ('10_days', '10 Dias'), ('14_days', '14 Dias'), 
        ('bi_weekly', 'Quincenal'), ('monthly', 'Mensual'), ('bi_monthly', 'Bimestral'),], 
        compute='_compute_l10n_mx_schedule_pay', store=True, readonly=False, required=True, string='Pago', default='weekly', index=True)

    @api.depends('beneficiario_ids', 'beneficiario_ids.porcentaje')
    def _compute_total_porcentaje(self):
        for contract in self:
            contract.total_porcentaje = sum(contract.beneficiario_ids.mapped('porcentaje'))

    @api.constrains('beneficiario_ids')
    def _check_total_porcentaje(self):
        for contract in self:
            total = sum(contract.beneficiario_ids.mapped('porcentaje'))
            if total > 100:
                raise ValidationError(_('El total de porcentajes de beneficiarios no puede exceder el 100%%. Actualmente es %s%%.') % total)

    def action_report_contract(self):
        if self.contract_type_id.name == 'Obra determinada':
            return self.env.ref('hr_extra.action_report_hrcontract_obra').report_action(self)
        else:
            return self.env.ref('hr_extra.action_report_hr_contract').report_action(self)

    def action_report_convenio(self):
        # Genera el convenio de confidencialidad
        return self.env.ref('hr_extra.action_report_convenio_confidencialidad').report_action(self)
