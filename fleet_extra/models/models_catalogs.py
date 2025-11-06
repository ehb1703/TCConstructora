# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import config

_logger = logging.getLogger(__name__)


class fleetTypeEquipment(models.Model):
    _name = 'fleet.type.equipment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Tipo de Equipo'
    _rec_name = 'name'

    name = fields.Char(string='Nombre')
    description = fields.Char(string='Descripción')
    active = fields.Boolean(string='Activo', default=True, required=True)

class fleetEdoEquipment(models.Model):
    _name = 'fleet.state.equipment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Estado del equipo'
    _rec_name = 'name'

    name = fields.Char(string='Nombre')
    description = fields.Char(string='Descripción')
    active = fields.Boolean(string='Activo', default=True, required=True)    
