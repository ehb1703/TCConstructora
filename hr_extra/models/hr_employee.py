# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class respartnerCurp(models.Model):
    _inherit = 'hr.employee'

    infonavit = fields.Char(string='Infonavit')
    fonacot = fields.Char(string='Fonacot')