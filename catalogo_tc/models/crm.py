# -*- coding: utf-8 -*-
import base64
import io
import os
import openpyxl
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

ENCABEZADOS = ('CÓDIGO', 'CODIGO', 'CLAVE')
ESTADOS = [('auto', 'Automático'), ('confirmado', 'Confirmado'), ('sugerido', 'Sugerido'), ('conflicto', 'Conflicto'), ('nuevo', 'Nuevo')]


class CrmLeadCatalogo(models.Model):
    _inherit = 'crm.lead'

    fuente_catalogo = fields.Char(string='Fuente de códigos', compute='_compute_fuente_catalogo', store=True, readonly=False,
        help='Banco de códigos del presupuesto de esta licitación. Por defecto la propia obra: el mismo código puede significar '
             'otra cosa en otra obra (MO05 es oficial fierrero en Zoquipan y ayudante electricista en La Higuera).')
    insumos_pendientes = fields.Integer(compute='_compute_insumos_pendientes', string='Insumos por conciliar')
    input_catalogo_ids = fields.One2many('crm.input.line', 'lead_id', string='Insumos', domain=[('es_encabezado', '=', False)],
        help='Renglones de la explosión de insumos sin el encabezado del archivo.')

    @api.depends('nombre_interno', 'name')
    def _compute_fuente_catalogo(self):
        for lead in self:
            # Una vez asignada no cambia: las equivalencias aprendidas quedan registradas con ella
            lead.fuente_catalogo = lead.fuente_catalogo or lead.nombre_interno or lead.name

    @api.depends('input_ids.conciliacion', 'input_ids.es_encabezado')
    def _compute_insumos_pendientes(self):
        # Todo lo que no está ligado al catálogo: también lo recién cargado que aún no se concilia
        for lead in self:
            lead.insumos_pendientes = len(lead.input_ids.filtered(lambda l: not l.es_encabezado and l.conciliacion not in ('auto', 'confirmado')))

    def _columnas_insumos(self):
        """Columna de la unidad con la regla del proceso original: si el renglón de referencia trae 'UNIDAD' en col3 es col3,
        si no col5 (formato de la explosión de insumos: Código, Concepto, Nacional, Extranjero, Unidad, Cantidad, Costo, Importe).
        El renglón de referencia es el encabezado cuando se guardó; si no, el primer renglón, como hace el proceso original."""
        self.ensure_one()
        # En pantalla (onchange) hay renglones sin guardar (NewId) que no se pueden comparar por id: los guardados van primero por su id
        # y los nuevos después, en el orden en que se capturaron
        lineas = self.input_ids.sorted(lambda l: (not l._origin.id, l._origin.id or 0))
        referencia = lineas.filtered('es_encabezado')[:1] or lineas[:1]
        unidad = 'col3' if (referencia.col3 or '').strip().upper() == 'UNIDAD' else 'col5'
        return referencia.filtered('es_encabezado'), unidad

    def action_cargar_insumos(self):
        """Carga la explosión de insumos desde el renglón de encabezado ('Código'). Lee el encabezado para saber dónde está el Importe,
        así entran los dos formatos que usa TC: Materiales (Código, Concepto, Nacional, Extranjero, Unidad, Cantidad, Costo, Importe)
        y Mano de obra / Equipo (Código, Concepto, Unidad, Cantidad, Costo, Importe). Guarda el encabezado como primer renglón para que
        la detección de columnas del proceso original funcione con ambos. Sustituye la carga de project_extra, que hoy falla."""
        for record in self:
            if not record.input_file:
                raise ValidationError(_('Seleccione un archivo para cargar.'))
            if record.input_ids:
                raise ValidationError(_('Ya hay información cargada. En caso de ser necesario volver a cargar debe eliminarlos.'))
            if os.path.splitext(record.input_filename or '')[1].lower() not in ('.xlsx', '.xlsm'):
                raise ValidationError(_('Seleccione un archivo tipo xlsx o xlsm'))
            libro = openpyxl.load_workbook(io.BytesIO(base64.b64decode(record.input_file)), data_only=True, read_only=True)
            nombres = ['col1', 'col2', 'col3', 'col4', 'col5', 'col6', 'col7', 'col8']
            registros, col_importe = [], None
            for fila in libro[libro.sheetnames[0]].iter_rows(values_only=True):
                celdas = ['' if v is None else str(v).strip() for v in (list(fila) + [None] * 8)[:8]]
                if col_importe is None:
                    if celdas[0].upper() in ENCABEZADOS:
                        textos = [c.upper() for c in celdas]
                        col_importe = textos.index('IMPORTE') if 'IMPORTE' in textos else 7
                        registros.append((0, 0, dict(zip(nombres, celdas))))
                    continue
                if celdas[0] and celdas[col_importe]:
                    registros.append((0, 0, dict(zip(nombres, celdas))))
            if len(registros) < 2:
                raise ValidationError(_('No se encontraron insumos: el archivo debe tener un renglón con el encabezado "Código" y renglones con importe.'))
            record.write({'input_ids': registros})
        return True

    def action_genera_insumos(self):
        """Reemplaza la creación de un producto por cada código de obra: concilia cada insumo contra el catálogo único."""
        for lead in self:
            codigos = [l.col1 for l in lead.input_ids]
            repetidos = {c for c in codigos if c and codigos.count(c) > 1}
            if repetidos:
                raise UserError(_('Existen conceptos repetidos favor de revisar el archivo.'))
            encabezado, col_unidad = lead._columnas_insumos()
            motor = self.env['catalogo.motor']
            memoria = motor.memoria()
            for linea in lead.input_ids.filtered(lambda l: not l.es_encabezado and l.conciliacion not in ('auto', 'confirmado')):
                estado, producto, motivo = motor.buscar(memoria, linea.col1, linea.col2, linea[col_unidad])
                vals = {'conciliacion': estado, 'motivo_conciliacion': motivo, 'sugerencia_id': producto.id if estado in ('sugerido', 'conflicto') else False}
                linea.write(vals)
                if estado == 'auto':
                    linea._ligar_insumo(producto, col_unidad)
        return True

    def action_confirmar_sugerencias(self):
        for lead in self:
            for linea in lead.input_ids.filtered(lambda l: l.conciliacion == 'sugerido'):
                linea.action_confirmar_sugerencia()


class CrmInputLineCatalogo(models.Model):
    _inherit = 'crm.input.line'

    conciliacion = fields.Selection(ESTADOS, string='Conciliación', copy=False)
    sugerencia_id = fields.Many2one('product.template', string='Sugerencia', copy=False)
    motivo_conciliacion = fields.Char(string='Motivo', copy=False)
    es_encabezado = fields.Boolean(compute='_compute_es_encabezado', store=True, string='Encabezado del archivo')
    unidad_obra = fields.Char(compute='_compute_unidad_obra', string='Unidad')

    @api.depends('col1')
    def _compute_es_encabezado(self):
        # El encabezado se reconoce por su texto: el cargador original no lo guarda, así que el primer renglón puede ser un insumo real
        for linea in self:
            linea.es_encabezado = (linea.col1 or '').strip().upper() in ENCABEZADOS

    @api.depends('col3', 'col5', 'lead_id.input_ids')
    def _compute_unidad_obra(self):
        columnas = {}
        for linea in self:
            if linea.lead_id.id not in columnas:
                columnas[linea.lead_id.id] = linea.lead_id._columnas_insumos()[1] if linea.lead_id else 'col3'
            linea.unidad_obra = linea[columnas[linea.lead_id.id]]

    def _ligar_insumo(self, producto, col_unidad=None):
        """Liga el renglón al insumo del catálogo, aprende la equivalencia y deja las marcas que exige 'Cotizaciones'."""
        Eq = self.env['catalogo.equivalencia'].sudo()
        motor = self.env['catalogo.motor']
        for linea in self:
            fuente = linea.lead_id.fuente_catalogo or linea.lead_id.name
            col_unidad = col_unidad or linea.lead_id._columnas_insumos()[1]
            cod = motor.normalizar(linea.col1)
            existe = Eq.search([('fuente_norm', '=', motor.normalizar(fuente)), ('codigo_norm', '=', cod)], limit=1) if cod else Eq
            if not existe:
                Eq.create({'fuente': fuente, 'codigo_externo': linea.col1 or False, 'descripcion_externa': linea.col2 or linea.col1,
                           'unidad_externa': linea[col_unidad], 'product_tmpl_id': producto.id, 'lead_id': linea.lead_id.id})
            elif existe.product_tmpl_id != producto:
                raise UserError(_('El código %(c)s de %(f)s ya apunta a %(p)s.', c=linea.col1, f=fuente, p=existe.product_tmpl_id.display_name))
            linea.write({'input_id': producto.id, 'input_ex': True, 'account_ex': bool(producto.property_account_expense_id),
                         'tipinsumo_ex': bool(producto.tipo_insumo_id), 'conciliacion': linea.conciliacion if linea.conciliacion == 'auto' else 'confirmado'})

    def action_confirmar_sugerencia(self):
        for linea in self:
            if linea.conciliacion not in ('sugerido', 'conflicto') or not linea.sugerencia_id:
                raise UserError(_('El renglón %s no tiene una sugerencia que confirmar.', linea.col1 or ''))
            if linea.conciliacion == 'conflicto' and not self.env.user.has_group('catalogo_tc.group_admin_catalogo'):
                raise UserError(_('Un conflicto de código solo lo resuelve el Administrador del Catálogo.'))
            linea._ligar_insumo(linea.sugerencia_id)

    def action_rechazar_sugerencia(self):
        self.write({'conciliacion': 'nuevo', 'sugerencia_id': False, 'motivo_conciliacion': _('Sugerencia rechazada')})

    def action_alta_insumo(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Alta de insumo'), 'res_model': 'catalogo.alta.wizard', 'view_mode': 'form', 'target': 'new',
                'context': {'default_linea_id': self.id}}
