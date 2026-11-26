# -*- coding: utf-8 -*-
import collections
import difflib
from odoo import api, models

# Unidad del presupuesto -> (nombres aceptados en Odoo, categoría de unidad preferida). Lo que no esté aquí se reporta, no se inventa.
UNIDADES = {
    'PZA': (('PZA',), 'Unit'), 'PIEZA': (('PZA',), 'Unit'), 'JGO': (('JGO',), 'Unit'), 'HOJA': (('HOJA',), 'Unit'), 'SALIDA': (('SALIDA', 'SAL'), 'Unit'),
    'M': (('M',), 'Length / Distance'), 'ML': (('M',), 'Length / Distance'), 'M2': (('M2',), 'Surface'), 'M3': (('M3',), 'Volume'),
    'KG': (('KG',), 'Weight'), 'TON': (('TON', 'TONELADAS'), 'Weight'), 'LT': (('LT',), 'Volume'),
    'HR': (('HR',), 'Service'), 'HOR': (('HR',), 'Service'), 'JOR': (('JOR',), 'Service'), 'R/DIA': (('DIA',), 'Working Time'),
}
TIPO_POR_GRUPO = {'MATERIALES': '001', 'MANO DE OBRA': '002', 'EQUIPO Y HERRAMIENTA': '003', 'SUBCONTRATOS': '004'}


class CatalogoImportador(models.AbstractModel):
    _name = 'catalogo.importador'
    _description = 'Importador del catálogo de insumos (base TC y equivalencias)'

    @api.model
    def unidad(self, nombre):
        motor = self.env['catalogo.motor']
        regla = UNIDADES.get(motor.normalizar(nombre))
        if not regla:
            return self.env['uom.uom']
        nombres, categoria = regla
        cands = self.env['uom.uom'].with_context(active_test=False).search([]).filtered(lambda u: motor.normalizar(u.name) in nombres and u.active)
        preferidas = cands.filtered(lambda u: u.category_id.name == categoria)
        return (preferidas or cands).sorted('id')[:1]

    @api.model
    def _catalogo(self, modelo, codigo, nombre, reporte, campo_nombre='name'):
        Modelo = self.env[modelo].with_context(active_test=False)
        rec = Modelo.search([('codigo', '=', codigo)], limit=1)
        motor = self.env['catalogo.motor']
        if rec:
            actual, propuesto = motor.normalizar(rec[campo_nombre]), motor.normalizar(nombre)
            if actual != propuesto:
                if difflib.SequenceMatcher(None, actual, propuesto).ratio() >= 0.85:   # errata: mismo concepto
                    reporte['nombres_parecidos'].append('%s %s: Odoo "%s" / base "%s" (se conserva Odoo)' % (modelo.split('.')[1], codigo, rec[campo_nombre], nombre))
                    return rec
                # el número ya significa otra cosa en Odoo: no se mezcla (lo resuelve el Administrador del Catálogo)
                reporte['codigo_ocupado'].append('%s %s: en Odoo es "%s" y en la base "%s"' % (modelo.split('.')[1], codigo, rec[campo_nombre], nombre))
                return Modelo.browse()
            return rec
        return Modelo.create({'codigo': codigo, campo_nombre: motor.normalizar(nombre)})

    @api.model
    def importar(self, filas):
        """filas: dicts con obra, codigo, tc (GG-CCC-FFF-NNNN), grupo, cat, fam, prod, unidad y, si se tiene, desc (concepto original de la obra).
        Aplica las reglas del catálogo: un producto por insumo (une idénticos), adopta lo que ya existe, nunca crea unidades ni duplica equivalencias."""
        env = self.sudo().env
        motor = env['catalogo.motor']
        Producto = env['product.template'].with_context(active_test=False)
        Eq = env['catalogo.equivalencia'].with_context(active_test=False)
        reporte = collections.defaultdict(list)
        cuenta = collections.Counter()
        iva = env['account.tax'].search([('type_tax_use', '=', 'purchase'), ('amount', '=', 16), ('company_id', '=', env.company.id)], limit=1)
        grupos = collections.OrderedDict()
        for f in sorted(filas, key=lambda x: x['tc']):
            llave = (motor.normalizar(f['grupo']), f['tc'][3:6], f['tc'][7:10], motor.normalizar(f['prod']), motor.normalizar(f['unidad']))
            grupos.setdefault(llave, []).append(f)
        for (grupo, ccc, fff, prod, uni), fs in grupos.items():
            principal = fs[0]
            claves = sorted({x['tc'] for x in fs})
            if len(claves) > 1:
                reporte['unidos'].append('%s: %s se unen en %s' % (prod, ', '.join(claves), claves[0]))
            tipo_cod = TIPO_POR_GRUPO.get(grupo)
            if not tipo_cod:
                reporte['sin_tipo'].append('%s (%s)' % (prod, ', '.join(claves)))
                continue
            # El catálogo (tipo, categoría, familia y combinación) se registra completo aunque el insumo no pueda cargarse
            tipo = env['product.tipo.insumo'].search([('codigo', '=', tipo_cod)], limit=1) or env['product.tipo.insumo'].create({'codigo': tipo_cod, 'nombre': grupo})
            cat = self._catalogo('product.categoria.insumo', ccc, principal['cat'], reporte)
            fam = self._catalogo('product.familia.insumo', fff, principal['fam'], reporte)
            if not cat or not fam:
                reporte['bloqueados'].append('%s (%s): su categoría o familia choca con otra en Odoo' % (prod, ', '.join(claves)))
                continue
            if not env['catalogo.categoria.familia'].search_count([('categoria_id', '=', cat.id), ('familia_id', '=', fam.id)]):
                env['catalogo.categoria.familia'].create({'categoria_id': cat.id, 'familia_id': fam.id})
            clave = '%05d' % int(claves[0][-4:])
            codigos_obra = [x['codigo'] for x in fs if x.get('codigo')]
            producto = Producto.search([('clave_insumo', '=', clave)], limit=1)
            if producto and not self._mismo_insumo(producto.name, prod):
                reporte['clave_con_otro_nombre'].append('%s: en Odoo la clave %s es "%s"; no se toca' % (prod, clave, producto.name))
                continue
            if not producto and codigos_obra:
                # Adopta la carga anterior que usaba el código de la obra como referencia, SOLO si el nombre confirma que es el mismo insumo:
                # el mismo código significa otra cosa en otra obra (MO05 es oficial fierrero en Zoquipan y ayudante electricista en La Higuera)
                candidatos = Producto.search([('active', '=', True), ('purchase_ok', '=', True), ('clave_insumo', '=', False), ('default_code', 'in', codigos_obra)])
                producto = candidatos.filtered(lambda c: self._mismo_insumo(c.name, prod))[:1]
                for otro in candidatos - producto:
                    reporte['codigo_con_otro_insumo'].append('%s [%s] no se adopta como %s (%s): otro insumo con el mismo código' % (otro.name, otro.default_code, prod, clave))
            uom = self.unidad(uni)
            if not uom and not producto:
                reporte['sin_unidad'].append('%s (%s, %s)' % (prod, uni, ', '.join(claves)))
                continue
            if not uom:   # ya existe en Odoo con su propia unidad: se adopta sin inventar ni cambiar unidades
                reporte['adoptado_sin_unidad'].append('%s (%s en la base, %s en Odoo, %s)' % (prod, uni, producto.uom_id.name, clave))
            vals = {'tipo_insumo_id': tipo.id, 'categoria_insumo_id': cat.id, 'familia_insumo_id': fam.id, 'clave_insumo': clave}
            if producto:
                producto.write(vals)
                cuenta['adoptados'] += 1
            else:
                vals.update({'name': prod, 'uom_id': uom.id, 'uom_po_id': uom.id, 'type': 'consu' if tipo_cod == '001' else 'service',
                             'purchase_ok': True, 'sale_ok': False, 'supplier_taxes_id': [(6, 0, iva.ids)]})
                if tipo.cuenta_gasto_id:
                    vals['property_account_expense_id'] = tipo.cuenta_gasto_id.id
                producto = Producto.create(vals)
                cuenta['creados'] += 1
            self._retirar_copias(producto, ['%05d' % int(c[-4:]) for c in claves[1:]], codigos_obra, reporte, cuenta)
            for x in fs:
                cod = motor.normalizar(x.get('codigo'))
                desc = x.get('desc') or x['prod']
                if Eq.search_count([('fuente_norm', '=', motor.normalizar(x['obra'])), ('codigo_norm', '=', cod or False), ('descripcion_norm', '=', motor.normalizar(desc))]):
                    continue
                if cod and Eq.search_count([('fuente_norm', '=', motor.normalizar(x['obra'])), ('codigo_norm', '=', cod)]):
                    reporte['codigo_repetido'].append('%s %s ya apunta a otro insumo' % (x['obra'], cod))
                    continue
                Eq.create({'fuente': x['obra'], 'codigo_externo': x.get('codigo') or False, 'descripcion_externa': desc,
                           'unidad_externa': x['unidad'], 'product_tmpl_id': producto.id})
                cuenta['equivalencias'] += 1
        self._ajustar_secuencia()
        reporte['cuenta'] = dict(cuenta)
        return dict(reporte)

    @api.model
    def _mismo_insumo(self, nombre_odoo, nombre_base):
        # Mismo insumo: mismos atributos y mayoría de palabras en común, o nombres casi idénticos (erratas de captura).
        motor = self.env['catalogo.motor']
        a, b = motor.normalizar(nombre_odoo), motor.normalizar(nombre_base)
        return a == b or motor.confirma(a, b) or difflib.SequenceMatcher(None, a, b).ratio() >= 0.85

    @api.model
    def _referencias(self, producto):
        #Dónde se usa el producto en el resto del sistema (todos los campos que apuntan a productos, sin contar el propio catálogo).
        env = self.sudo().env
        variantes = producto.with_context(active_test=False).product_variant_ids
        usos = []
        for campo in env['ir.model.fields'].search([('ttype', '=', 'many2one'), ('store', '=', True), ('relation', 'in', ('product.template', 'product.product'))]):
            if campo.model in ('product.template', 'product.product', 'catalogo.equivalencia', 'catalogo.alta.wizard') or campo.model not in env \
                    or env[campo.model]._abstract or env[campo.model]._transient or campo.name not in env[campo.model]._fields:
                continue
            ids = producto.ids if campo.relation == 'product.template' else variantes.ids
            n = env[campo.model].with_context(active_test=False).search_count([(campo.name, 'in', ids)]) if ids else 0
            if n:
                usos.append('%s.%s: %s' % (campo.model, campo.name, n))
        return usos

    @api.model
    def _retirar_copias(self, producto, claves_unidas, codigos_obra, reporte, cuenta):
        """Copias que una carga anterior dejó de un insumo que la base une en uno solo: se archivan si nadie las usa;
        si ya tienen movimientos se reportan para que el Administrador del Catálogo decida."""
        Producto = self.sudo().env['product.template'].with_context(active_test=False)
        dominio = [('id', '!=', producto.id), ('active', '=', True), '|', ('clave_insumo', 'in', claves_unidas or ['-']), ('default_code', 'in', codigos_obra or ['-'])]
        for copia in Producto.search(dominio):
            if not (copia.clave_insumo in claves_unidas or self._mismo_insumo(copia.name, producto.name)):
                continue   # mismo código de obra pero otro insumo (MO05 en otra obra): no es una copia
            usos = self._referencias(copia)
            if usos:
                reporte['copias_con_movimientos'].append('%s [%s] copia de %s: %s' % (copia.name, copia.default_code, producto.clave_insumo_tc, ', '.join(usos)))
                reporte['copias_con_movimientos_ids'].append(copia.id)
                continue
            copia.write({'active': False})
            cuenta['copias_archivadas'] += 1
            reporte['copias_archivadas'].append('%s [%s] se archiva: el insumo es %s' % (copia.name, copia.default_code, producto.clave_insumo_tc))

    @api.model
    def _ajustar_secuencia(self):
        usados = self.env['product.template'].sudo().with_context(active_test=False).search([('clave_insumo', '!=', False)]).mapped('clave_insumo')
        maximo = max([int(c) for c in usados if c.isdigit()] or [0])
        seq = self.env['ir.sequence'].sudo().search([('code', '=', 'catalogo.insumo.clave')], limit=1)
        if seq and seq.number_next_actual <= maximo:
            seq.number_next = maximo + 1