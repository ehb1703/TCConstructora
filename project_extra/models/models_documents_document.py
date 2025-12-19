# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class DocumentsDocument(models.Model):
    _inherit = 'documents.document'

    @api.model_create_multi
    def create(self, vals_list):
        # Crear los documentos primero
        documents = super(DocumentsDocument, self).create(vals_list)
        # Procesar cada documento creado
        for doc in documents:
            # Solo procesar si es un archivo (no carpeta) y está en una carpeta
            if doc.type == 'folder':
                continue
                
            if not doc.folder_id:
                continue
            
            resultado = self._auto_vincular_crm_lead(doc)
        return documents


    def write(self, vals):
        # Override write para vincular cuando se mueve un documento a carpeta CRM
        res = super(DocumentsDocument, self).write(vals)
        if 'folder_id' in vals or 'attachment_id' in vals:
            for doc in self:
                if doc.type != 'folder':
                    self._auto_vincular_crm_lead(doc)
        return res

    def _get_folder_hierarchy(self, documento):
        """ Obtiene la jerarquía de carpetas de un documento.
        Returns: tuple (carpeta_actual, carpeta_padre, carpeta_abuelo) o (None, None, None) """
        try:
            # Obtener la carpeta del documento
            folder = documento.folder_id if hasattr(documento, 'folder_id') else None
            if not folder:
                return None, None, None
            
            # Obtener carpeta padre (licitación)
            parent_folder = folder.folder_id if hasattr(folder, 'folder_id') else None
            if not parent_folder:
                return folder, None, None
            
            # Obtener carpeta abuelo (CRM)
            grandparent_folder = parent_folder.folder_id if hasattr(parent_folder, 'folder_id') else None
            return folder, parent_folder, grandparent_folder
            
        except Exception as e:
            _logger.error("Error obteniendo jerarquía de carpetas: %s", str(e))
            return None, None, None


    def _auto_vincular_crm_lead(self, documento):
        """Vincula automáticamente un documento con su CRM Lead basándose en la estructura de carpetas.
        Estructura esperada: CRM / <nombre_licitacion> / (Tecnico|Economico)
        
        Returns:
            bool: True si se vinculó exitosamente, False en caso contrario """
        try:
            if documento.res_model == 'crm.lead' and documento.res_id:
                return False
            
            folder, lic_folder, crm_folder = self._get_folder_hierarchy(documento)
            if not folder:
                return False
            
            # Verificar si está en carpeta Tecnico o Economico
            folder_name = (folder.name or '').strip()
            if folder_name not in ['Tecnico', 'Economico']:
                return False
            if not lic_folder:
                return False
            if not crm_folder:
                return False
                
            crm_folder_name = (crm_folder.name or '').strip()
            if crm_folder_name != 'CRM':
                return False
            
            # Buscar el lead que corresponde a esta carpeta
            Lead = self.env['crm.lead'].sudo()
            lic_name = (lic_folder.name or '').strip()
            # Buscar por no_licitacion o por name
            lead = Lead.search(['|', ('no_licitacion', '=', lic_name), ('name', '=', lic_name)], limit=1)
            if not lead:
                return False
            
            # Vincular el documento
            documento.sudo().write({'res_model': 'crm.lead', 'res_id': lead.id,})
            tipo_carpeta = folder.name
            lead.message_post(
                body=_("📎 Nuevo documento agregado en <b>%s</b>: %s") % (tipo_carpeta, documento.name),
                message_type='notification',
                subtype_xmlid='mail.mt_note')
            return True
            
        except Exception as e:
            import traceback
            return False
