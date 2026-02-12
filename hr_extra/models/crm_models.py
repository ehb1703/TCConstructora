# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class crmInheritState(models.Model):
    _inherit = 'crm.lead'
    
    visita_personas_ids = fields.Many2many('hr.employee', 'crm_lead_visita_employee_rel', 'lead_id', 'employee_id', string='Personas visita', 
        domain="[('state', '!=', 'baja')]")
    bases_supervisor_id = fields.Many2one('hr.employee', string='Supervisor general', tracking=True, 
        domain="[('state', '!=', 'baja')]")
    junta_personas_ids = fields.Many2many('hr.employee', 'crm_lead_junta_employee_rel', 'lead_id', 'employee_id', string='Personas junta', 
        domain="[('state', '!=', 'baja')]")
    tecnico_documental_id = fields.Many2one('hr.employee', 'Técnico/documental', tracking=True, domain="[('state', '!=', 'baja')]")
    economico_operativo_id = fields.Many2one('hr.employee', 'Económico/operativo', tracking=True, domain="[('state', '!=', 'baja')]")
    apertura_personas_ids = fields.Many2many('hr.employee', 'crm_lead_apertura_employee_rel', 'lead_id', 'employee_id', string='Personas Apertura', 
        domain="[('state', '!=', 'baja')]")
    fallo_personas_ids = fields.Many2many('hr.employee', 'crm_lead_fallo_employee_rel', 'lead_id', 'employee_id', string='Personas fallo', 
        domain="[('state', '!=', 'baja')]")

class CrmPropuestaTecnicaRevisionInherit(models.Model):
    _inherit = 'crm.propuesta.tecnica.revision'
    
    employee_id = fields.Many2one('hr.employee', string='Nombre', required=True, domain="[('state', '!=', 'baja')]")

class CrmPropuestaEconomicaRevisionInherit(models.Model):
    _inherit = 'crm.propuesta.economica.revision'
    
    employee_ids = fields.Many2many('hr.employee', 'crm_pe_revision_employee_rel', 'revision_id', 'employee_id', string='Nombre', 
        domain="[('state', '!=', 'baja')]")

class projectResidentes(models.Model):
    _inherit = 'project.residents'
    
    resident_id = fields.Many2one('hr.employee', string='Residente de Obra', domain="[('state', '!=', 'baja'), ('job_id.name', 'ilike', 'RESIDENTE')]")
