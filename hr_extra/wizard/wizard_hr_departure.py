# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import ValidationError, UserError

class HrDepartureWizard(models.TransientModel):
    _inherit = 'hr.departure.wizard'
    
    def action_register_departure(self):
        employee = self.employee_id.sudo()
        if employee.state == 'activo':
            current_contract = employee.sudo().contract_id
            if current_contract and current_contract.date_start > self.departure_date:
                raise UserError(_('La fecha de salida no puede ser anterior a la fecha de inicio del contrato actual.'))

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
                    employee.sudo().contract_ids.filtered(lambda c: c.state == 'draft').write({'state': 'cancel'})
                    if current_contract and current_contract.state in ['open', 'draft']:
                        current_contract.sudo().write({'date_end': self.departure_date})
                    if current_contract.state == 'open':
                        current_contract.sudo().write({'state': 'close'})

                if self.release_campany_car:
                    self._free_campany_car()

                if self.unassign_equipment:
                    employee.sudo().update({'equipment_ids': [Command.unlink(equipment.id) for equipment in self.employee_id.equipment_ids]})

                for rec in employee.obra_ids.filtered(lambda c: not c.fecha_fin):
                    rec.update({'fecha_fin': self.departure_date})
                    if not rec.fecha_inicio:
                        rec.update({'fecha_inicio': self.departure_date})
