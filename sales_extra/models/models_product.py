# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class supplyProductTemplate(models.Model):
    _inherit = 'product.template'
    
    type_supply = fields.Selection(selection=[('int','Interna'), ('ext','Externa')],
        string='Tipo de Aprovisionamiento', default='ext')