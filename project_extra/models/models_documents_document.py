# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class DocumentsDocument(models.Model):
    _inherit = 'documents.document'

    @api.model_create_multi
    def create(self, vals_list):
        documents = super(DocumentsDocument, self).create(vals_list)
        for doc in documents:
            if doc.type == 'folder' or not doc.folder_id:
                continue
            self._auto_vincular_crm_lead(doc)
        return documents

    def write(self, vals):
        res = super(DocumentsDocument, self).write(vals)
        if 'folder_id' in vals or 'attachment_id' in vals:
            for doc in self:
                if doc.type != 'folder':
                    self._auto_vincular_crm_lead(doc)
        return res

    def _get_folder_hierarchy(self, documento):
        try:
            folder = documento.folder_id
            if not folder:
                return None, None, None

            parent_folder = folder.folder_id
            if not parent_folder:
                return folder, None, None

            grandparent_folder = parent_folder.folder_id
            return folder, parent_folder, grandparent_folder
        except Exception as e:
            _logger.error("Error obteniendo jerarquía de carpetas: %s", str(e))
            return None, None, None


    def _auto_vincular_crm_lead(self, documento):
        try:
            if documento.res_model == 'crm.lead' and documento.res_id:
                return False

            folder, lic_folder, crm_folder = self._get_folder_hierarchy(documento)
            if not folder:
                return False

            folder_name = (folder.name or '').strip()
            if folder_name not in ['Tecnico', 'Economico']:
                return False
            if not lic_folder or not crm_folder:
                return False
            if (crm_folder.name or '').strip() != 'CRM':
                return False

            lic_name = (lic_folder.name or '').strip()
            lead = self.env['crm.lead'].sudo().search(['|', ('no_licitacion', '=', lic_name), ('name', '=', lic_name)], limit=1)
            if not lead:
                return False

            documento.sudo().write({'res_model': 'crm.lead', 'res_id': lead.id})
            lead.message_post(
                body=_('Nuevo documento agregado en %s: %s') % (folder.name, documento.name),
                message_type='notification',
                subtype_xmlid='mail.mt_note')
            return True

        except Exception as e:
            _logger.error('Error vinculando documento con CRM Lead: %s', str(e))
            return False
