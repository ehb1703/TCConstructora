# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import ValidationError, UserError

class HrDepartureWizard(models.TransientModel):
    _inherit = 'hr.departure.wizard'
    
    def action_register_departure(self):
        # Esperar que comenta Arturo
        employee = self.employee_id
        if employee.state == 'activo':
            current_contract = self.sudo().employee_id.contract_id
            if current_contract and current_contract.date_start > self.departure_date:
                raise UserError(_("Departure date can't be earlier than the start date of current contract."))

            if self.departure_reason_id.name.upper() in ['RETIRO']:
                description = 'pensionado'
            elif self.departure_reason_id.name.upper() in ['DESPEDIDO', 'RENUNCIA']:
                description = 'baja'
            elif self.departure_reason_id.name.upper() in ['ENFERMEDAD']:
                description = 'incapacidad' 
            else:
                description = 'permiso'

            employee.state = description
            employee.departure_reason_id = self.departure_reason_id
            employee.departure_description = self.departure_description
            employee.departure_date = self.departure_date

            if description in ('baja', 'pensionado'):
                if self.set_date_end:
                    self.sudo().employee_id.contract_ids.filtered(lambda c: c.state == 'draft').write({'state': 'cancel'})
                    if current_contract and current_contract.state in ['open', 'draft']:
                        self.sudo().employee_id.contract_id.write({'date_end': self.departure_date})
                    if current_contract.state == 'open':
                        current_contract.state = 'close'

                if self.release_campany_car:
                    self._free_campany_car()

                if self.unassign_equipment:
                    self.employee_id.update({'equipment_ids': [Command.unlink(equipment.id) for equipment in self.employee_id.equipment_ids]})
