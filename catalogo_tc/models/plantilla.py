# -*- coding: utf-8 -*-
import base64
import collections
import difflib
import io
import re
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from odoo import api, models, _
from odoo.exceptions import UserError

from .importador import UNIDADES

HOJA = 'INSUMOS'
# Columnas obligatorias de la plantilla, en este orden exacto (la plantilla es la única forma aceptada de subir insumos)
COLUMNAS = [('clave', 'CLAVE TC'), ('tipo', 'TIPO'), ('categoria', 'CATEGORIA'), ('familia', 'FAMILIA'), ('nombre', 'NOMBRE DEL INSUMO'),
            ('unidad', 'UNIDAD'), ('obra', 'OBRA'), ('codigo_obra', 'CODIGO EN LA OBRA'), ('descripcion_obra', 'DESCRIPCION EN LA OBRA')]
OBLIGATORIAS = ('tipo', 'categoria', 'familia', 'nombre', 'unidad')
CLAVE = re.compile(r'^\s*(\d{2,3})-(\d{3})-(\d{3})-(\d{4,5})\s*$')
CODIGO = re.compile(r'^\s*(\d{1,3})(\s*-.*)?$')
MAX_ERRORES = 200


class CatalogoPlantilla(models.AbstractModel):
    _inherit = 'catalogo.importador'

    @api.model
    def generar_plantilla(self):
        # Excel oficial para subir insumos, con las listas vigentes de Odoo (tipos, categorías, familias, combinaciones y unidades).
        env = self.sudo().env
        libro = openpyxl.Workbook()
        negrita, fondo = Font(bold=True, color='FFFFFF'), PatternFill('solid', fgColor='1E5A8A')
        hoja = libro.active
        hoja.title = HOJA
        for i, (_c, titulo) in enumerate(COLUMNAS, 1):
            celda = hoja.cell(row=1, column=i, value=titulo)
            celda.font, celda.fill, celda.alignment = negrita, fondo, Alignment(horizontal='center', vertical='center', wrap_text=True)
        for letra, ancho in zip('ABCDEFGHI', (20, 26, 34, 34, 50, 10, 18, 20, 50)):
            hoja.column_dimensions[letra].width = ancho
        hoja.freeze_panes = 'A2'

        def lista(nombre, filas, encabezados):
            h = libro.create_sheet(nombre)
            h.append(encabezados)
            for c in h[1]:
                c.font, c.fill = negrita, fondo
            for f in filas:
                h.append(list(f))
            for i in range(1, len(encabezados) + 1):
                h.column_dimensions[openpyxl.utils.get_column_letter(i)].width = 45 if i == 1 else 30
            return len(filas) + 1

        tipos = env['product.tipo.insumo'].search([], order='codigo')
        cats = env['product.categoria.insumo'].search([], order='codigo')
        fams = env['product.familia.insumo'].search([], order='codigo')
        n_t = lista('TIPOS', [('%s - %s' % (t.codigo, t.nombre),) for t in tipos], ['TIPO'])
        n_c = lista('CATEGORIAS', [('%s - %s' % (c.codigo, c.name),) for c in cats], ['CATEGORIA'])
        n_f = lista('FAMILIAS', [('%s - %s' % (f.codigo, f.name),) for f in fams], ['FAMILIA'])
        combos = env['catalogo.categoria.familia'].search([]).sorted(lambda x: (x.categoria_id.codigo, x.familia_id.codigo))
        lista('COMBINACIONES', [('%s - %s' % (x.categoria_id.codigo, x.categoria_id.name), '%s - %s' % (x.familia_id.codigo, x.familia_id.name)) for x in combos],
              ['CATEGORIA', 'FAMILIA PERMITIDA'])
        n_u = lista('UNIDADES', [(u,) for u in sorted(UNIDADES)], ['UNIDAD'])
        for col, hoja_lista, n in (('B', 'TIPOS', n_t), ('C', 'CATEGORIAS', n_c), ('D', 'FAMILIAS', n_f), ('F', 'UNIDADES', n_u)):
            # Dentro del archivo la fórmula va SIN '=' (con '=' Excel lo marca como contenido dañado y pide repararlo)
            dv = DataValidation(type='list', formula1="%s!$A$2:$A$%d" % (hoja_lista, max(n, 2)), allow_blank=True, showErrorMessage=True,
                                errorTitle='Valor no válido', error='Elija un valor de la lista (hoja %s).' % hoja_lista)
            hoja.add_data_validation(dv)
            dv.add('%s2:%s10000' % (col, col))

        ins = libro.create_sheet('INSTRUCCIONES', 0)
        textos = [
            'PLANTILLA OFICIAL PARA SUBIR INSUMOS AL CATÁLOGO ÚNICO DE TC',
            '',
            'Llene solo la hoja INSUMOS, un insumo por renglón, desde el renglón 2. No cambie, mueva ni borre los encabezados.',
            'Obligatorias: TIPO, CATEGORIA, FAMILIA, NOMBRE DEL INSUMO y UNIDAD. Elíjalas de las listas desplegables.',
            'CLAVE TC: déjela vacía para que Odoo asigne el siguiente consecutivo. Si el insumo ya tiene clave, escríbala completa (ej. 001-006-014-00028);',
            '          sus tres primeras partes deben coincidir con TIPO, CATEGORIA y FAMILIA.',
            'La FAMILIA debe estar permitida para la CATEGORIA (hoja COMBINACIONES). Una combinación nueva la autoriza el Administrador del Catálogo al importar.',
            'UNIDAD: solo las de la hoja UNIDADES. Unidades como MIL, PIE TAB, % o %MO no se aceptan: conviértalas antes de subir.',
            'OBRA, CODIGO EN LA OBRA y DESCRIPCION EN LA OBRA son opcionales: guardan cómo llama cada obra a este insumo (equivalencia).',
            '          Si escribe CODIGO EN LA OBRA, OBRA es obligatoria.',
            'No repita insumos: el mismo NOMBRE con la misma UNIDAD dos veces en el archivo es un error.',
            '',
            'En Odoo: Compras > Productos > Importar insumos. Primero "Validar" (no guarda nada y muestra los errores por renglón); si no hay errores, "Importar".',
            'Si un solo renglón tiene error no se importa nada: corrija y vuelva a validar.',
            '',
            'Ejemplo de renglón (no lo copie a la hoja INSUMOS):',
        ]
        for t in textos:
            ins.append([t])
        ins.append([titulo for _c, titulo in COLUMNAS])
        muestra = env['product.template'].search([('clave_insumo', '!=', False), ('equivalencia_ids', '!=', False)], limit=1)
        eq = muestra.equivalencia_ids[:1]
        ins.append([muestra.clave_insumo_tc or '', '%s - %s' % (muestra.tipo_insumo_id.codigo, muestra.tipo_insumo_id.nombre),
                    '%s - %s' % (muestra.categoria_insumo_id.codigo, muestra.categoria_insumo_id.name),
                    '%s - %s' % (muestra.familia_insumo_id.codigo, muestra.familia_insumo_id.name), muestra.name or '', (muestra.uom_id.name or '').upper(),
                    eq.fuente or '', eq.codigo_externo or '', eq.descripcion_externa or ''] if muestra else [''])
        ins['A1'].font = Font(bold=True, size=14, color='1E5A8A')
        ins.column_dimensions['A'].width = 140
        libro.active = 1
        for h in libro.worksheets:   # una sola pestaña seleccionada: la que se llena
            h.sheet_view.tabSelected = h.title == HOJA
        salida = io.BytesIO()
        libro.save(salida)
        return salida.getvalue()

    
    @api.model
    def leer_plantilla(self, contenido_b64):
        try:
            libro = openpyxl.load_workbook(io.BytesIO(base64.b64decode(contenido_b64)), data_only=True, read_only=True)
        except Exception:
            raise UserError(_('El archivo no es un Excel (.xlsx) válido. Use la plantilla oficial.'))
        if HOJA not in libro.sheetnames:
            raise UserError(_('El archivo no usa la plantilla oficial: falta la hoja "%s". Descargue la plantilla desde Odoo.', HOJA))
        filas = list(libro[HOJA].iter_rows(values_only=True))
        motor = self.env['catalogo.motor']
        esperado = [titulo for _c, titulo in COLUMNAS]
        encabezado = [motor.normalizar(v) for v in (list(filas[0]) if filas else [])[:len(COLUMNAS)]]
        if encabezado != [motor.normalizar(t) for t in esperado]:
            raise UserError(_('El archivo no usa la plantilla oficial: los encabezados de la hoja INSUMOS deben ser exactamente\n%(e)s\ny el archivo trae\n%(a)s',
                              e=' | '.join(esperado), a=' | '.join(str(v or '') for v in (filas[0] if filas else []))))
        renglones = []
        for n, fila in enumerate(filas[1:], 2):
            valores = ['' if v is None else (str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)).strip() for v in (list(fila) + [None] * 9)[:9]]
            if any(valores):
                renglones.append(dict(zip([c for c, _t in COLUMNAS], valores), fila=n))
        if not renglones:
            raise UserError(_('La hoja INSUMOS no tiene renglones.'))
        return renglones

    
    @api.model
    def _codigo(self, texto):
        m = CODIGO.match(texto or '')
        return m and m.group(1).zfill(3)

    @api.model
    def importar_plantilla(self, contenido_b64, solo_validar=True):
        # Valida TODO el archivo; si hay un solo error no escribe nada. Devuelve el reporte (errores por renglón o lo que se hizo).
        env = self.sudo().env
        motor = env['catalogo.motor']
        renglones = self.leer_plantilla(contenido_b64)
        Producto = env['product.template'].with_context(active_test=False)
        tipos = {t.codigo: t for t in env['product.tipo.insumo'].search([])}
        cats = {c.codigo: c for c in env['product.categoria.insumo'].search([])}
        fams = {f.codigo: f for f in env['product.familia.insumo'].search([])}
        combos = {(x.categoria_id.id, x.familia_id.id) for x in env['catalogo.categoria.familia'].search([])}
        por_clave = {p.clave_insumo: p for p in Producto.search([('clave_insumo', '!=', False)])}
        por_nombre = {(motor.normalizar(p.name), p.uom_id.id): p for p in Producto.search([('clave_insumo', '!=', False), ('active', '=', True)])}
        eqs = {(e.fuente_norm, e.codigo_norm): e for e in env['catalogo.equivalencia'].search([('codigo_norm', '!=', False)])}
        errores, listos = [], []
        vistos_nombre, vistos_clave, vistos_eq = {}, {}, {}

        def error(r, col, msg):
            errores.append({'fila': r['fila'], 'columna': dict(COLUMNAS).get(col, col), 'mensaje': msg})

        for r in renglones:
            antes = len(errores)
            for col in OBLIGATORIAS:
                if not r[col]:
                    error(r, col, _('Es obligatoria.'))
            tipo, cat, fam = tipos.get(self._codigo(r['tipo'])), cats.get(self._codigo(r['categoria'])), fams.get(self._codigo(r['familia']))
            if r['tipo'] and not tipo:
                error(r, 'tipo', _('"%s" no es un tipo del catálogo (hoja TIPOS).', r['tipo']))
            if r['categoria'] and not cat:
                error(r, 'categoria', _('"%s" no es una categoría del catálogo (hoja CATEGORIAS).', r['categoria']))
            if r['familia'] and not fam:
                error(r, 'familia', _('"%s" no es una familia del catálogo (hoja FAMILIAS).', r['familia']))
            uom = self.unidad(r['unidad']) if r['unidad'] else env['uom.uom']
            if r['unidad'] and not uom:
                error(r, 'unidad', _('"%(u)s" no es una unidad aceptada. Use una de: %(l)s.', u=r['unidad'], l=', '.join(sorted(UNIDADES))))
            if r['codigo_obra'] and not r['obra']:
                error(r, 'obra', _('Es obligatoria cuando se escribe CODIGO EN LA OBRA.'))
            clave = None
            if r['clave']:
                m = CLAVE.match(r['clave'])
                if not m:
                    error(r, 'clave', _('"%s" no tiene el formato de Clave TC (ej. 001-006-014-00028).', r['clave']))
                else:
                    clave = '%05d' % int(m.group(4))
                    if tipo and cat and fam and (m.group(1).zfill(3), m.group(2), m.group(3)) != (tipo.codigo, cat.codigo, fam.codigo):
                        error(r, 'clave', _('La clave %(c)s no coincide con TIPO/CATEGORIA/FAMILIA (%(t)s-%(a)s-%(f)s).', c=r['clave'], t=tipo.codigo, a=cat.codigo, f=fam.codigo))
                    existente = por_clave.get(clave)
                    if existente and r['nombre'] and not self._mismo_insumo(existente.name, r['nombre']):
                        error(r, 'clave', _('La clave %(c)s ya es del insumo "%(n)s".', c=clave, n=existente.name))
                    if clave in vistos_clave:
                        error(r, 'clave', _('La clave se repite en el renglón %s.', vistos_clave[clave]))
                    vistos_clave.setdefault(clave, r['fila'])
            llave = (motor.normalizar(r['nombre']), uom.id)
            if r['nombre'] and uom:
                if llave in vistos_nombre:
                    error(r, 'nombre', _('El insumo se repite en el renglón %s (mismo nombre y unidad).', vistos_nombre[llave]))
                vistos_nombre.setdefault(llave, r['fila'])
            if r['codigo_obra'] and r['obra']:
                k = (motor.normalizar(r['obra']), motor.normalizar(r['codigo_obra']))
                if k in vistos_eq:
                    error(r, 'codigo_obra', _('El código de esta obra se repite en el renglón %s.', vistos_eq[k]))
                vistos_eq.setdefault(k, r['fila'])
                previa = eqs.get(k)
                if previa and r['nombre'] and not self._mismo_insumo(previa.product_tmpl_id.name, r['nombre']):
                    error(r, 'codigo_obra', _('En la obra %(o)s el código %(c)s ya es del insumo "%(n)s".', o=r['obra'], c=r['codigo_obra'], n=previa.product_tmpl_id.name))
            if len(errores) == antes:
                listos.append(dict(r, tipo_rec=tipo, cat_rec=cat, fam_rec=fam, uom_rec=uom, clave_num=clave, llave=llave))
            if len(errores) >= MAX_ERRORES:
                break

        reporte = {'renglones': len(renglones), 'errores': errores, 'creados': 0, 'ya_existian': 0, 'adoptados': 0, 'adoptados_por_nombre': 0,
                   'copias_archivadas': 0, 'copias_con_uso': [], 'equivalencias': 0,
                   'combinaciones': 0, 'validado': not errores, 'importado': False, 'detalle': []}
        if errores or solo_validar:
            reporte['sin_errores_listos'] = len(listos)
            return reporte

        iva = env['account.tax'].search([('type_tax_use', '=', 'purchase'), ('amount', '=', 16), ('company_id', '=', env.company.id)], limit=1)
        # Carga masiva: sin bitácora de cambios por registro y creando por lotes (5,000 insumos deben caber en una petición web)
        rapido = {'tracking_disable': True, 'mail_create_nolog': True, 'mail_create_nosubscribe': True, 'mail_notrack': True}
        Producto = Producto.with_context(**rapido)
        Eq = env['catalogo.equivalencia'].with_context(**rapido)
        with env.cr.savepoint():
            for r in listos:
                cat, fam = r['cat_rec'], r['fam_rec']
                if (cat.id, fam.id) not in combos:
                    env['catalogo.categoria.familia'].create({'categoria_id': cat.id, 'familia_id': fam.id})
                    combos.add((cat.id, fam.id))
                    reporte['combinaciones'] += 1
            # 1) se resuelve cada renglón: insumo existente, producto anterior a adoptar o alta nueva
            nuevos, destino = [], {}
            adopciones = collections.defaultdict(list)
            if any(r['codigo_obra'] for r in listos):
                for p in Producto.search([('active', '=', True), ('purchase_ok', '=', True), ('clave_insumo', '=', False),
                                          ('default_code', 'in', [r['codigo_obra'] for r in listos if r['codigo_obra']])]):
                    adopciones[p.default_code].append(p)
            # productos anteriores al catálogo (sin Clave TC) por nombre y unidad: el mismo insumo se adopta aunque el renglón no traiga código de obra
            sin_clave, copias, ref_anterior = collections.defaultdict(list), {}, {}
            for p in Producto.search([('active', '=', True), ('purchase_ok', '=', True), ('clave_insumo', '=', False)], order='id'):
                sin_clave[(motor.normalizar(p.name), motor.unidad_canonica(p.uom_id.name))].append(p)
            for r in listos:
                existente = por_clave.get(r['clave_num']) if r['clave_num'] else por_nombre.get(r['llave'])
                if existente:
                    destino[r['fila']] = existente
                    reporte['ya_existian'] += 1
                    continue
                previo = next((p for p in adopciones.get(r['codigo_obra'], []) if self._mismo_insumo(p.name, r['nombre'])), None)
                if previo and previo not in destino.values():
                    destino[r['fila']] = previo
                    reporte['adoptados'] += 1
                    continue
                iguales = [p for p in sin_clave.get((motor.normalizar(r['nombre']), motor.unidad_canonica(r['uom_rec'].name)), [])
                           if p not in destino.values()]
                if iguales:
                    # el más antiguo recibe la clave; los demás iguales son copias de cargas anteriores
                    destino[r['fila']] = iguales[0]
                    copias[iguales[0].id] = iguales[1:]
                    for p in iguales:
                        ref_anterior[p.id] = p.default_code
                    reporte['adoptados'] += 1
                    reporte['adoptados_por_nombre'] += 1
                    continue
                nuevos.append(r)
            # 2) claves: las que trae el archivo se respetan; las que faltan salen de un bloque consecutivo reservado de una vez
            faltan = [r for r in nuevos if not r['clave_num']] + [r for r in listos if destino.get(r['fila']) and not destino[r['fila']].clave_insumo]
            if faltan:
                seq = env['ir.sequence'].search([('code', '=', 'catalogo.insumo.clave')], limit=1)
                env.cr.execute('SELECT number_next FROM ir_sequence WHERE id = %s FOR UPDATE', (seq.id,))
                siguiente = env.cr.fetchone()[0]   # la fila queda bloqueada: dos cargas o altas simultáneas no reciben las mismas claves
                usados = [int(c) for c in Producto.search([('clave_insumo', '!=', False)]).mapped('clave_insumo') if c.isdigit()]
                inicio = max(max(usados or [0]) + 1, siguiente)
                for n, r in enumerate(faltan):
                    r['clave_num'] = '%05d' % (inicio + n)
                env.cr.execute('UPDATE ir_sequence SET number_next = %s WHERE id = %s', (inicio + len(faltan), seq.id))
            def clasificacion(r):
                return {'tipo_insumo_id': r['tipo_rec'].id, 'categoria_insumo_id': r['cat_rec'].id, 'familia_insumo_id': r['fam_rec'].id,
                        'clave_insumo': r['clave_num'], 'default_code': '%s-%s-%s-%s' % (r['tipo_rec'].codigo, r['cat_rec'].codigo, r['fam_rec'].codigo, r['clave_num'])}
            # 3) existentes y adoptados: solo se escribe si su clasificación cambia
            for r in listos:
                p = destino.get(r['fila'])
                if not p:
                    continue
                vals = clasificacion(dict(r, clave_num=p.clave_insumo or r['clave_num']))
                if any((p[c].id if hasattr(p[c], 'id') else p[c]) != v for c, v in vals.items()):
                    p.write(vals)
            # 4) altas nuevas por lotes
            for k in range(0, len(nuevos), 500):
                lote = nuevos[k:k + 500]
                vals_list = []
                for r in lote:
                    tipo, uom = r['tipo_rec'], r['uom_rec']
                    vals = dict(clasificacion(r), name=motor.normalizar(r['nombre']), uom_id=uom.id, uom_po_id=uom.id, purchase_ok=True, sale_ok=False,
                                type='consu' if tipo.codigo == '001' else 'service', supplier_taxes_id=[(6, 0, iva.ids)])
                    if tipo.cuenta_gasto_id:
                        vals['property_account_expense_id'] = tipo.cuenta_gasto_id.id
                    vals_list.append(vals)
                for r, p in zip(lote, Producto.create(vals_list)):
                    destino[r['fila']] = p
                    por_clave[p.clave_insumo] = p
                    por_nombre[r['llave']] = p
                reporte['creados'] += len(lote)
            # 4b) copias de cargas anteriores: se archivan si nadie las usa; con movimientos se reportan (decide el Administrador del Catálogo)
            retiro, cuenta = collections.defaultdict(list), collections.Counter()
            for r in listos:
                p = destino.get(r['fila'])
                for copia in (copias.get(p.id, []) if p else []):
                    self._retirar(copia, p, retiro, cuenta)
            reporte['copias_archivadas'] = cuenta['copias_archivadas']
            reporte['copias_con_uso'] = retiro['copias_con_movimientos']
            # 5) equivalencias de obra por lotes
            eq_vals = []
            # la referencia anterior de lo adoptado por nombre (p. ej. MA0001) se conserva como equivalencia: buscarla sigue encontrando el insumo
            for r in listos:
                p = destino.get(r['fila'])
                for anterior in ([p] + copias.get(p.id, [])) if p and p.id in copias else []:
                    ref = ref_anterior.get(anterior.id)
                    k = ('REFERENCIA ANTERIOR EN ODOO', motor.normalizar(ref))
                    if ref and k not in eqs:
                        eqs[k] = True
                        eq_vals.append({'fuente': 'REFERENCIA ANTERIOR EN ODOO', 'codigo_externo': ref, 'descripcion_externa': anterior.name,
                                        'unidad_externa': anterior.uom_id.name, 'product_tmpl_id': p.id})
            for r in listos:
                if r['codigo_obra'] and r['obra']:
                    k = (motor.normalizar(r['obra']), motor.normalizar(r['codigo_obra']))
                    if k not in eqs:
                        eqs[k] = True
                        eq_vals.append({'fuente': r['obra'], 'codigo_externo': r['codigo_obra'], 'descripcion_externa': r['descripcion_obra'] or r['nombre'],
                                        'unidad_externa': r['unidad'], 'product_tmpl_id': destino[r['fila']].id})
            for k in range(0, len(eq_vals), 1000):
                Eq.create(eq_vals[k:k + 1000])
            reporte['equivalencias'] = len(eq_vals)
            self._ajustar_secuencia()
        reporte['importado'] = True
        return reporte