# -*- coding: utf-8 -*-
import re
import unicodedata
from odoo import api, models

# Pulgadas comunes -> milimetros nominales (2" y 50 mm son la misma tuberia)
PULG_MM = {'1/2': 13, '3/4': 19, '1': 25, '1 1/4': 32, '1 1/2': 38, '2': 50, '2 1/2': 64, '3': 75, '4': 100, '6': 150, '8': 200}
GRADOS = {'1RA', '2DA', '3RA', 'PRIMERA', 'SEGUNDA', 'TERCERA'}
VACIAS = {'CON', 'PARA', 'TIPO', 'MARCA', 'SIMILAR', 'INCLUYE', 'DEL', 'LOS', 'LAS', 'UNA', 'POR', 'SIN'}
# Formas de escribir la misma unidad en presupuestos y en Odoo -> unidad canónica (PZA = PIEZA = Unidades, M3 = m³, etc.)
ALIAS_UNIDAD = {'PZA': 'PZA', 'PZAS': 'PZA', 'PZ': 'PZA', 'PIEZA': 'PZA', 'PIEZAS': 'PZA', 'UNIDAD': 'PZA', 'UNIDADES': 'PZA', 'UNITS': 'PZA', 'UNIT': 'PZA', 'U': 'PZA',
                'M': 'M', 'ML': 'M', 'MTS': 'M', 'MT': 'M', 'METRO': 'M', 'METROS': 'M', 'M2': 'M2', 'MTS2': 'M2', 'M3': 'M3', 'MTS3': 'M3',
                'KG': 'KG', 'KGS': 'KG', 'KILO': 'KG', 'KILOS': 'KG', 'KILOGRAMO': 'KG', 'KILOGRAMOS': 'KG', 'TON': 'TON', 'TONELADA': 'TON', 'TONELADAS': 'TON',
                'LT': 'LT', 'LTS': 'LT', 'L': 'LT', 'LITRO': 'LT', 'LITROS': 'LT', 'HR': 'HR', 'HRS': 'HR', 'HOR': 'HR', 'HORA': 'HR', 'HORAS': 'HR',
                'JOR': 'JOR', 'JORNADA': 'JOR', 'DIA': 'DIA', 'DIAS': 'DIA', 'R/DIA': 'DIA', 'JGO': 'JGO', 'JUEGO': 'JGO', 'SAL': 'SALIDA', 'SALIDA': 'SALIDA'}


class CatalogoMotor(models.AbstractModel):
    _name = 'catalogo.motor'
    _description = 'Motor de emparejamiento del catálogo de insumos'

    @api.model
    def normalizar(self, texto):
        # Mayúsculas, sin acentos (conserva la Ñ), comillas rectas y espacios normalizados.
        salida = []
        for ch in str(texto or '').upper():
            if ch == 'Ñ':
                salida.append(ch)
                continue
            salida.append(''.join(c for c in unicodedata.normalize('NFD', ch) if unicodedata.category(c) != 'Mn'))
        texto = ''.join(salida).replace('”', '"').replace('“', '"').replace("''", '"').replace('´', "'").replace('’', "'")
        return ' '.join(texto.split())


    @api.model
    def firma(self, texto):
        # Atributos que distinguen variantes: medidas (pulgadas a mm), calibres, potencias, grados y demás números.
        s = self.normalizar(texto).replace('CAL.', 'CAL ').replace('Ø', ' ').replace('NO.', '#')
        out = set()
        for pulg, mm in PULG_MM.items():
            patron = r'(?<![\d/])' + re.escape(pulg) + r'\s*(?:"|PULG)'
            if re.search(patron, s):
                out.add('%dMM' % mm)
                s = re.sub(patron, ' ', s)
        
        for num, uni in re.findall(r'(\d+(?:\.\d+)?)\s?(MM|CM|KG|KV|HP|M2|M3|M|LT|TON)\b', s):
            valor = float(num)
            out.add('%dMM' % round(valor * 10 if uni == 'CM' else valor) if uni in ('MM', 'CM') else '%s%s' % (num, uni))
            s = s.replace(num, ' ', 1)
        out |= {'N%s' % n for n in re.findall(r'\b\d+(?:\.\d+)?\b', s)}
        out |= {g for g in GRADOS if re.search(r'\b%s\b' % g, s)}
        return frozenset(out)

    @api.model
    def palabras(self, texto):
        return {w for w in re.findall(r'[A-ZÑ]{3,}', self.normalizar(texto)) if w not in VACIAS}

    @api.model
    def parecido(self, a, b):
        pa, pb = self.palabras(a), self.palabras(b)
        return len(pa & pb) / len(pa | pb) if pa | pb else 0.0

    @api.model
    def confirma(self, desc_a, desc_b):
        # Dos descripciones son el mismo insumo si tienen los mismos atributos y comparten la mayoría de las palabras.
        return self.firma(desc_a) == self.firma(desc_b) and self.parecido(desc_a, desc_b) >= 0.5

    @api.model
    def unidad_canonica(self, texto):
        u = self.normalizar(texto).replace('³', '3').replace('²', '2').replace('.', '').replace(' ', '')
        return ALIAS_UNIDAD.get(u, u)

    @api.model
    def memoria(self):
        # Lo que el catálogo ya sabe: descripciones (de equivalencias y de productos) -> insumo, y código externo -> equivalencias.
        por_desc, por_codigo, candidatos = {}, {}, []
        for eq in self.env['catalogo.equivalencia'].search([('estado', '=', 'confirmada')]):
            uni = self.unidad_canonica(eq.unidad_norm)
            por_desc.setdefault((eq.descripcion_norm, uni), eq.product_tmpl_id)
            if eq.codigo_norm:
                por_codigo.setdefault(eq.codigo_norm, []).append(eq)
            candidatos.append((eq.descripcion_norm, uni, eq.product_tmpl_id))
        for producto in self.env['product.template'].search([('clave_insumo', '!=', False)]):
            uni = self.unidad_canonica(producto.uom_id.name)
            por_desc.setdefault((self.normalizar(producto.name), uni), producto)
            candidatos.append((self.normalizar(producto.name), uni, producto))
        # Productos que ya existían en Odoo antes del catálogo (sin Clave TC): nunca se ligan solos, se sugieren para clasificarlos
        sin_clave = {}
        for producto in self.env['product.template'].search([('clave_insumo', '=', False), ('purchase_ok', '=', True)], order='id'):
            sin_clave.setdefault(self.normalizar(producto.name), []).append(producto)
        return {'desc': por_desc, 'codigo': por_codigo, 'candidatos': candidatos, 'sin_clave': sin_clave}

    @api.model
    def buscar(self, memoria, codigo, descripcion, unidad, umbral=0.6):
        """Cascada probada con datos reales (pila de pruebas, vuelta 3): devuelve (estado, producto, motivo).
        estado: auto | sugerido | conflicto | nuevo"""
        desc, uni, cod = self.normalizar(descripcion), self.unidad_canonica(unidad), self.normalizar(codigo)
        producto = memoria['desc'].get((desc, uni))
        if producto:
            return 'auto', producto, 'Descripción idéntica'
        previas = memoria['codigo'].get(cod, []) if cod else []
        confirmadas = [eq for eq in previas if self.confirma(eq.descripcion_externa, desc)]
        if confirmadas:
            return 'auto', confirmadas[0].product_tmpl_id, 'Código %s ya conocido (%s) y la descripción coincide' % (cod, confirmadas[0].fuente)
        firma, mejor, puntaje = self.firma(desc), None, 0.0
        for d, u, prod in memoria['candidatos']:
            if u == uni and self.firma(d) == firma:
                p = self.parecido(desc, d)
                if p > puntaje:
                    mejor, puntaje = prod, p
        if mejor and puntaje >= umbral:
            return 'sugerido', mejor, 'Mismos atributos y %d%% de palabras en común' % round(puntaje * 100)
        if previas:
            return 'conflicto', previas[0].product_tmpl_id, 'El código %s ya existe en %s con otra descripción' % (cod, previas[0].fuente)
        viejos = memoria.get('sin_clave', {}).get(desc, [])
        if viejos:
            misma = [p for p in viejos if self.unidad_canonica(p.uom_id.name) == uni]
            producto = (misma or viejos)[0]
            return 'sugerido', producto, 'Ya existe en Odoo sin Clave TC%s: clasifíquelo con "Alta de insumo"' % (
                '' if misma else ' (en Odoo con unidad %s)' % producto.uom_id.name)
        return 'nuevo', self.env['product.template'], 'Sin coincidencias en el catálogo'