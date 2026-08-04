# -*- coding: utf-8 -*-
from odoo import _, http
from odoo.http import request
import io
import xlsxwriter
import base64

class controller_cuadro_comparativo(http.Controller):

        @http.route('/web/binary/purchase_cuadro_comparativo', type='http', auth='public')
        def purchase_cuadro_comparativo(self, lead, **kw):
                output = io.BytesIO()
                wb = xlsxwriter.Workbook(output)
                ws = wb.add_worksheet('Comparativo')

                encabezado_style = wb.add_format({'font_name': 'Arial', 'font_color': 'black', 'bold': 1, 'valign': 'center', 'align': 'center', 'top': 1, 'bottom': 1, 'left': 1, 'right': 1})
                style = wb.add_format({'font_name': 'Arial', 'font_color': 'black', 'bold': 0, 'valign': 'center', 'align': 'left', 'top': 1, 'bottom': 1, 'left': 1, 'right': 1})
                style_centrado = wb.add_format({'font_name': 'Arial', 'font_color': 'black', 'bold': 0, 'valign': 'center', 'align': 'center', 'top': 1, 'bottom': 1, 'left': 1, 'right': 1})
                style_moneda = wb.add_format({'font_name': 'Arial', 'bold': 0, 'valign': 'center', 'align': 'right', 'top': 1, 'bottom': 1, 'left': 1, 'right': 1, 'num_format': '$#,##0.00'})
                style_moneda_negrita = wb.add_format({'font_name': 'Arial', 'bold': 1, 'valign': 'center', 'align': 'right', 'top': 1, 'bottom': 1, 'left': 1, 'right': 1, 'num_format': '$#,##0.00'})
                style_numero = wb.add_format({'font_name': 'Arial', 'bold': 0, 'valign': 'vcenter', 'align': 'right', 'top': 1, 'bottom': 1, 'left': 1, 'right': 1, 'num_format': '#,##0.000000'})

                request.env.cr.execute('''SELECT cl.ID, cl.NAME, cl.NO_LICITACION, COUNT(*) FROM purchase_order po JOIN crm_lead cl ON po.LEAD_ID = cl.ID
                        WHERE po.TYPE_PURCHASE = 'ins' AND po.STATE = 'sent' AND po.LEAD_ID = ''' + str(lead) +
                        ' GROUP BY 1, 2, 3')
                num = request.env.cr.fetchall()

                if not num:
                        wb.close(); output.close()
                        return request.make_response(
                                u'No hay cotizaciones de insumos en estado "Enviada" para esta licitación.'.encode('utf-8'),
                                [('Content-Type', 'text/plain; charset=utf-8')])

                lead_id = num[0][0]

                request.env.cr.execute('''SELECT (case when UPPER(col5) = 'CANTIDAD' then 'col5' else 'col6' end)
                        FROM crm_input_line WHERE id = (SELECT MIN(id) FROM crm_input_line WHERE lead_id = ''' + str(lead_id) + ')')
                min_id = request.env.cr.fetchall()
                cantidad = min_id[0][0] if min_id else 'col6'

                request.env.cr.execute('SELECT COUNT(*) FROM crm_input_line WHERE lead_id = ' + str(lead_id))
                tiene_input_lines = request.env.cr.fetchall()[0][0] > 0

                # 4 columnas por proveedor: Precio Unitario, Subtotal, IVA, Total
                col = 3 + (num[0][3] * 4)
                ws.set_column(0, col, 15)
                fila = 3

                user = request.env['res.users'].sudo().browse(request.env.uid)
                logo = user.company_id.logo
                if logo:
                        logo_data = base64.b64decode(logo)
                        logo_path = '/tmp/logo.png'
                        with open(logo_path, 'wb') as f:
                                f.write(logo_data)
                        ws.insert_image('A1:B3', logo_path, {'x_scale': 0.7, 'y_scale': 0.7})

                ws.merge_range(0, 1, 0, col, u'CUADRO COMPARATIVO', encabezado_style)
                ws.merge_range(1, 1, 1, col, u'%s' % num[0][1], encabezado_style)
                ws.merge_range(2, 1, 2, col, u'%s' % num[0][2], encabezado_style)

                supplier_ids = request.env['purchase.order'].search([
                        ('state', '=', 'sent'), ('lead_id', '=', lead_id), ('type_purchase', '=', 'ins')
                ]).sorted(key=lambda r: r.name)

                for record in supplier_ids:
                        ws.write(fila, 0, u'No. de Cotización', encabezado_style)
                        ws.write(fila, 1, u'Proveedor', encabezado_style)
                        ws.merge_range(fila, 2, fila, col, record.partner_id.name, style)
                        fila += 1
                        ws.write(fila, 0, record.name, style_centrado)
                        ws.write(fila, 1, u'Subtotal sin IVA', encabezado_style)
                        ws.merge_range(fila, 2, fila, col, record.amount_untaxed, style_moneda)
                        fila += 1
                        ws.write(fila, 0, '', style_centrado)
                        ws.write(fila, 1, u'IVA 16%', encabezado_style)
                        ws.merge_range(fila, 2, fila, col, record.amount_tax, style_moneda)
                        fila += 1
                        ws.write(fila, 0, '', style_centrado)
                        ws.write(fila, 1, u'Total con IVA', encabezado_style)
                        ws.merge_range(fila, 2, fila, col, record.amount_total, style_moneda_negrita)
                        fila += 1

                fila += 1
                ws.merge_range(fila, 0, fila+1, 1, u'Insumo', encabezado_style)
                ws.merge_range(fila, 2, fila+1, 2, u'Unidad', encabezado_style)
                ws.merge_range(fila, 3, fila+1, 3, u'Cantidad', encabezado_style)
                colr = 4
                for record in supplier_ids:
                        ws.merge_range(fila, colr, fila, colr + 3, record.name, encabezado_style)
                        ws.write(fila+1, colr,     'Precio Unitario', encabezado_style)
                        ws.write(fila+1, colr + 1, 'Subtotal',        encabezado_style)
                        ws.write(fila+1, colr + 2, 'IVA',             encabezado_style)
                        ws.write(fila+1, colr + 3, 'Total',           encabezado_style)
                        colr += 4

                fila += 2

                if tiene_input_lines:
                        request.env.cr.execute('SELECT pp.id, pp.product_tmpl_id, round(cil.' + cantidad + '''::numeric, 6) qty, cil.id, MIN(pol.price_unit)
                                FROM crm_lead cl JOIN crm_input_line cil ON cl.ID = cil.LEAD_ID
                                JOIN product_product pp ON cil.input_id = pp.product_tmpl_id
                                JOIN purchase_order po ON cl.id = po.lead_id AND po.state = 'sent'
                                JOIN purchase_order_line pol ON po.id = pol.order_id AND pp.id = pol.product_id
                                WHERE cl.id = ''' + str(lead_id) + ' GROUP BY 1, 2, 3, 4 ORDER BY pp.DEFAULT_CODE')
                        product_ids = request.env.cr.fetchall()

                        for record in product_ids:
                                product = request.env['product.product'].browse(record[0])
                                ws.merge_range(fila, 0, fila, 1, u'[%s] %s' % (product.default_code or '', product.name), style)
                                ws.write(fila, 2, product.uom_id.name.upper() if product.uom_id else '', style_centrado)
                                ws.write(fila, 3, record[2], style_numero)

                                request.env.cr.execute('''SELECT COALESCE(pol.price_unit, 0), COALESCE(pol.price_subtotal, 0),
                                                COALESCE(pol.price_tax, 0), COALESCE(pol.price_total, 0)
                                        FROM crm_input_line cil JOIN purchase_order po ON cil.lead_id = po.lead_id
                                        LEFT JOIN purchase_order_line pol ON po.id = pol.order_id AND pol.product_id = ''' + str(record[0]) +
                                        ' WHERE cil.id = ' + str(record[3]) + " AND po.state = 'sent' ORDER BY po.name")
                                price = request.env.cr.fetchall()
                                min_price = record[4]
                                colr = 4
                                for x in price:
                                        estilo = style_moneda_negrita if x[0] == min_price else style_moneda
                                        ws.write(fila, colr,     x[0], estilo)
                                        ws.write(fila, colr + 1, x[1], estilo)
                                        ws.write(fila, colr + 2, x[2], estilo)
                                        ws.write(fila, colr + 3, x[3], estilo)
                                        colr += 4
                                fila += 1
                else:
                        request.env.cr.execute('''
                                SELECT pp.id, pol.product_qty, MIN(pol.price_unit)
                                FROM purchase_order po
                                JOIN purchase_order_line pol ON po.id = pol.order_id
                                JOIN product_product pp ON pol.product_id = pp.id
                                WHERE po.lead_id = ''' + str(lead_id) + ''' AND po.state = 'sent' AND po.type_purchase = 'ins'
                                GROUP BY pp.id, pol.product_qty ORDER BY pp.default_code''')
                        product_ids = request.env.cr.fetchall()

                        for record in product_ids:
                                product = request.env['product.product'].browse(record[0])
                                ws.merge_range(fila, 0, fila, 1, u'[%s] %s' % (product.default_code or '', product.name), style)
                                ws.write(fila, 2, product.uom_id.name.upper() if product.uom_id else '', style_centrado)
                                ws.write(fila, 3, record[1], style_numero)

                                request.env.cr.execute('''
                                        SELECT COALESCE(pol.price_unit, 0), COALESCE(pol.price_subtotal, 0),
                                               COALESCE(pol.price_tax, 0), COALESCE(pol.price_total, 0)
                                        FROM purchase_order po
                                        JOIN purchase_order_line pol ON po.id = pol.order_id AND pol.product_id = ''' + str(record[0]) +
                                        ' WHERE po.lead_id = ' + str(lead_id) + ''' AND po.state = 'sent' AND po.type_purchase = 'ins'
                                        ORDER BY po.name''')
                                price = request.env.cr.fetchall()
                                min_price = record[2]
                                colr = 4
                                for x in price:
                                        estilo = style_moneda_negrita if x[0] == min_price else style_moneda
                                        ws.write(fila, colr,     x[0], estilo)
                                        ws.write(fila, colr + 1, x[1], estilo)
                                        ws.write(fila, colr + 2, x[2], estilo)
                                        ws.write(fila, colr + 3, x[3], estilo)
                                        colr += 4
                                fila += 1

                wb.close()
                content = output.getvalue()
                output.close()

                return request.make_response(content,
                        [('Content-Type', 'application/octet-stream'),
                         ('Content-Disposition', 'attachment; filename=Cuadro_comparativo_%s.xlsx;' % num[0][2])])
