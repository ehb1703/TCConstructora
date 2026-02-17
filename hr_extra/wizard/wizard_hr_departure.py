# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import ValidationError, UserError

class HrDepartureWizard(models.TransientModel):
    _inherit = 'hr.departure.wizard'
    
    def action_register_departure(self):
        # Esperar que comenta Arturo
        employee = self.employee_id
        if employee.state == 'activo':
            if self.departure_reason_id.name in ['RETIRO']:
                description = 'pensionado'
            elif self.departure_reason_id.name in ['DESPIDO', 'RENUNCIA']:
                description = 'baja'
            elif self.departure_reason_id.name in ['ENFERMEDAD']:
                description = 'incapacidad' 
            else:
                description = 'permiso'

            employee.state = description
            employee.departure_reason_id = self.departure_reason_id
            employee.departure_description = self.departure_description
            employee.departure_date = self.departure_date
