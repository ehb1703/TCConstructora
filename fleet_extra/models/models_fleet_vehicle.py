# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import config

_logger = logging.getLogger(__name__)


class fleetVehicleModelInherit(models.Model):
    _inherit = 'fleet.vehicle.model'

    type_id = fields.Many2one('fleet.type.equipment', string='Tipo de Equipo')


class fleetVehicleInherit(models.Model):
    _inherit = 'fleet.vehicle'

    companyresg_id = fields.Many2one('res.company', string='Resguardante')
    companyaseg_id = fields.Many2one('res.company', string='Asegurado')