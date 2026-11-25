# -*- coding: utf-8 -*-
import base64
from markupsafe import Markup, escape
from odoo import fields, models, _
from odoo.exceptions import UserError

GRUPO_ADMIN = 'catalogo_tc.group_admin_catalogo'


class CatalogoImportarWizard(models.TransientModel):
    _name = 'catalogo.importar.wizard'
    _description = 'Importar insumos al catálogo con la plantilla oficial'

    archivo = fields.Binary(string='Archivo (plantilla oficial)')
    archivo_nombre = fields.Char(string='Nombre del archivo')
    estado = fields.Selection([('inicio', 'Inicio'), ('errores', 'Con errores'), ('validado', 'Validado'), ('importado', 'Importado')], default='inicio')
    resultado = fields.Html(string='Resultado', readonly=True, sanitize=False)

    def _reabrir(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'new',
                'name': _('Importar insumos')}

    def action_descargar_plantilla(self):
        contenido = self.env['catalogo.importador'].generar_plantilla()
        adjunto = self.env['ir.attachment'].create({'name': 'Plantilla_insumos_TC.xlsx', 'datas': base64.b64encode(contenido), 'res_model': self._name,
                                                    'res_id': self.id, 'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=true' % adjunto.id, 'target': 'self'}

    def _procesar(self, solo_validar):
        self.ensure_one()
        if not self.env.user.has_group(GRUPO_ADMIN):
            raise UserError(_('Solo el Administrador del Catálogo puede importar insumos.'))
        if not self.archivo:
            raise UserError(_('Seleccione el archivo llenado con la plantilla oficial.'))
        if not (self.archivo_nombre or '').lower().endswith(('.xlsx', '.xlsm')):
            raise UserError(_('El archivo debe ser Excel (.xlsx) generado desde la plantilla oficial.'))
        rep = self.env['catalogo.importador'].importar_plantilla(self.archivo, solo_validar=solo_validar)
        if rep['errores']:
            filas = Markup('').join(Markup('<tr><td>%s</td><td>%s</td><td>%s</td></tr>') % (e['fila'], e['columna'], e['mensaje']) for e in rep['errores'])
            self.write({'estado': 'errores', 'resultado': Markup(
                '<div class="alert alert-danger">No se importó nada: %s error(es) en %s renglones. Corrija el archivo y vuelva a validar.</div>'
                '<table class="table table-sm"><thead><tr><th>Renglón</th><th>Columna</th><th>Problema</th></tr></thead><tbody>%s</tbody></table>')
                % (len(rep['errores']), rep['renglones'], filas)})
        elif solo_validar:
            self.write({'estado': 'validado', 'resultado': Markup(
                '<div class="alert alert-success">Archivo correcto: %s renglones listos para importar. Presione <b>Importar</b>.</div>') % rep['renglones']})
        else:
            self.write({'estado': 'importado', 'archivo': False, 'resultado': Markup(
                '<div class="alert alert-success">Importación terminada (%s renglones).</div><ul>'
                '<li>Insumos nuevos con clave: <b>%s</b></li><li>Ya existían en el catálogo (se actualizó su clasificación): <b>%s</b></li>'
                '<li>Productos anteriores adoptados (recibieron su clave): <b>%s</b></li><li>Equivalencias de obra registradas: <b>%s</b></li>'
                '<li>Combinaciones categoría-familia autorizadas: <b>%s</b></li></ul>')
                % (rep['renglones'], rep['creados'], rep['ya_existian'], rep['adoptados'], rep['equivalencias'], rep['combinaciones'])})
        return self._reabrir()

    def action_validar(self):
        return self._procesar(solo_validar=True)

    def action_importar(self):
        return self._procesar(solo_validar=False)
