# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class Document(models.Model):
    _inherit = 'documents.document'

    lead_id = fields.Many2one('crm.lead', compute='_compute_lead_id', search='_search_lead_id', export_string_translation=False)
    lead_ids = fields.One2many('crm.lead', 'documents_folder_id', string='CRM') # for folders
    
    @api.depends('res_id', 'res_model')
    def _compute_lead_id(self):
        for record in self:
            if record.res_model == 'crm.lead':
                record.lead_id = self.env['crm.lead'].browse(record.res_id)
            else:
                record.lead_id = False

    @api.model
    def _search_lead_id(self, operator, value):
        if operator in ('=', '!=') and isinstance(value, bool): # needs to be the first condition as True and False are instances of int
            if not value:
                operator = operator == '=' and '!=' or '='
            comparator = operator == '=' and '|' or '&'
            return [comparator, ('res_model', operator, 'crm.lead')]
        elif operator in ('=', '!=', 'in', 'not in') and (isinstance(value, int) or isinstance(value, list)):
            return [('res_model', '=', 'crm.lead'), ('res_id', operator, value)]
        elif operator in ('ilike', 'not ilike', '=', '!=') and isinstance(value, str):
            query_lead = self.env['crm.lead']._search([(self.env['crm.lead']._rec_name, operator, value)])
            return [('id', 'in', SQL('''(WITH helper as (%s)
                SELECT document.id
                FROM documents_document document LEFT JOIN crm_lead lead ON lead.id = document.res_id AND document.res_model = 'crm.lead')''', 
                query_lead.subselect()))]
        else:
            raise ValidationError(_('Invalid lead search'))