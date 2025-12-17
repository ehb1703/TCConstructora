# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class hrEmployeeInherit(models.Model):
    _inherit = 'hr.employee'

    infonavit = fields.Char(string='Infonavit')
    fonacot = fields.Char(string='Fonacot')


class hrContractInherit(models.Model):
    _inherit = 'hr.contract'

    def action_report_contract(self):
        if self.contract_type_id.name == 'Obra determinada':
            return self.env.ref('hr_extra.action_report_hrcontract_obra').report_action(self)
        else:
            return self.env.ref('hr_extra.action_report_hr_contract').report_action(self)
