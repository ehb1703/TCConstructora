# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class DocumentsDocument(models.Model):
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
        
        # Si se cambió la carpeta, intentar vincular
        if 'folder_id' in vals:
            for doc in self:
                if doc.type != 'folder' and doc.folder_id:
                    self._auto_vincular_crm_lead(doc)
        
        return res


    def _auto_vincular_crm_lead(self, documento):
        """Vincula automáticamente un documento con su CRM Lead basándose en la estructura de carpetas.
        Estructura esperada: CRM / <nombre_licitacion> / (Tecnico|Economico)
        
        Returns:
            bool: True si se vinculó exitosamente, False en caso contrario """
        try:
            # Si ya está vinculado, no hacer nada
            if documento.res_model and documento.res_id:
                _logger.info("   ℹ️  Ya está vinculado: %s (ID: %s)", documento.res_model, documento.res_id)
                return False
            
            folder = documento.folder_id
            if not folder:
                return False
            
            # Verificar si está en carpeta Tecnico o Economico
            if folder.name not in ['Tecnico', 'Economico']:
                return False
            
            # Obtener carpeta padre (carpeta de licitación)
            lic_folder = folder.folder_id
            if not lic_folder:
                return False
            
            # Obtener carpeta abuelo (debe ser CRM)
            crm_folder = lic_folder.folder_id
            if not crm_folder:
                return False
                
            if crm_folder.name != 'CRM':
                return False
            
            # Buscar el lead que corresponde a esta carpeta
            Lead = self.env['crm.lead'].sudo()
            lic_name = lic_folder.name
            
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
