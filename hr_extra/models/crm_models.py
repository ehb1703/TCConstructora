# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class crmInheritState(models.Model):
    _inherit = 'crm.lead'
    
    visita_personas_ids = fields.Many2many('hr.employee', 'crm_lead_visita_employee_rel', 'lead_id', 'employee_id', string='Personas visita', 
        domain="[('state', '!=', 'baja'), ('finiquito', '=', False)]")
    bases_supervisor_id = fields.Many2one('hr.employee', string='Supervisor general', tracking=True, 
        domain="[('state', '!=', 'baja'), ('finiquito', '=', False)]")
    tecnico_documental_id = fields.Many2one('hr.employee', 'Técnico/documental', tracking=True, domain="[('state', '!=', 'baja'), ('finiquito', '=', False)]")
    economico_operativo_id = fields.Many2one('hr.employee', 'Económico/operativo', tracking=True, domain="[('state', '!=', 'baja'), ('finiquito', '=', False)]")
    apertura_personas_ids = fields.Many2many('hr.employee', 'crm_lead_apertura_employee_rel', 'lead_id', 'employee_id', string='Personas Apertura', 
        domain="[('state', '!=', 'baja'), ('finiquito', '=', False)]")
    fallo_personas_ids = fields.Many2many('hr.employee', 'crm_lead_fallo_employee_rel', 'lead_id', 'employee_id', string='Personas fallo', 
        domain="[('state', '!=', 'baja'), ('finiquito', '=', False)]")


class CrmPropuestaTecnicaRevisionInherit(models.Model):
    _inherit = 'crm.propuesta.tecnica.revision'
    
    employee_id = fields.Many2one('hr.employee', string='Nombre', required=True, domain="[('state', '!=', 'baja'), ('finiquito', '=', False)]")


class CrmPropuestaEconomicaRevisionInherit(models.Model):
    _inherit = 'crm.propuesta.economica.revision'
    
    employee_ids = fields.Many2many('hr.employee', 'crm_pe_revision_employee_rel', 'revision_id', 'employee_id', string='Nombre', 
        domain="[('state', '!=', 'baja'), ('finiquito', '=', False)]")


class projectResidentes(models.Model):
    _inherit = 'project.residents'
    
    resident_id = fields.Many2one('hr.employee', string='Residente de Obra', domain="[('state', '!=', 'baja'), ('finiquito', '=', False), ('job_id.name', 'ilike', 'RESIDENTE')]")


class projectResidentes(models.Model):
    _inherit = 'crm.analyst'
    
    employee_id = fields.Many2one('hr.employee', string='Empleado interno', domain="[('state', '!=', 'baja'), ('finiquito', '=', False)]", tracking=True)


class projectObraInherit(models.Model):
    _inherit = 'project.project'
    
    def write(self, vals):
        if 'name' in vals:
            if vals.get('name') != self.name:
                self.env.cr.execute("UPDATE hr_employee SET current_project_name = '{}' WHERE current_project_name = '{}' ".format(vals.get('name'), self.name))

        super(projectObraInherit, self).write(vals)


class crmStageTypeBills(models.Model):
    _inherit = 'crm.stage'
    
    email_ids = fields.Many2many('hr.employee', string='Distribución de correo', domain="[('state', '!=', 'baja'), ('finiquito', '=', False)]")        
