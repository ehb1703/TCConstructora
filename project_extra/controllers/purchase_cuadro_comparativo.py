# -*- coding: utf-8 -*-
from odoo import _, http
from odoo.http import request
from datetime import datetime
import io
import xlsxwriter
import base64
import pytz

class controller_cuadro_comparativo(http.Controller):

	@http.route('/web/binary/purchase_cuadro_comparativo', type='http', auth='public')
	def purchase_cuadro_comparativo(self, lead, **kw):
		output = io.BytesIO()        
		wb = xlsxwriter.Workbook(output)
		ws = wb.add_worksheet('Comparativo')

		encabezado_style =  wb.add_format({'font_name': 'Arial', 'font_color': 'black', 'bold': 1, 'valign': 'center', 'align': 'center', 'top': 1,
		    'bottom': 1, 'left': 1, 'right': 1})
		style =  wb.add_format({'font_name': 'Arial', 'font_color': 'black', 'bold': 0, 'valign': 'center', 'align': 'left', 'top': 1, 'bottom': 1, 
		    'left': 1, 'right': 1})
		style_centrado =  wb.add_format({'font_name': 'Arial', 'font_color': 'black', 'bold': 0, 'valign': 'center', 'align': 'center', 'top': 1, 'bottom': 1, 
		    'left': 1, 'right': 1})
		style_moneda = wb.add_format({'font_name': 'Arial', 'bold': 0, 'valign': 'center', 'align': 'right', 'top': 1, 'bottom': 1, 'left': 1, 'right': 1,
            'num_format': '$#,##0.00'})
		style_moneda_negrita = wb.add_format({'font_name': 'Arial', 'bold': 1, 'valign': 'center', 'align': 'right', 'top': 1, 'bottom': 1, 'left': 1, 'right': 1,
            'num_format': '$#,##0.00'})
		style_numero = wb.add_format({'font_name': 'Arial', 'bold': 0, 'valign': 'vcenter', 'align': 'right', 'top': 1, 'bottom': 1, 'left': 1, 'right': 1,
            'num_format': '#,##0.000000'})
		"""encabezado_verde =  wb.add_format({'font_name': 'Arial', 'font_color': 'black', 'bold': 1, 'valign': 'center', 'align': 'center', 'top': 1,
		    'bottom': 1, 'left': 1, 'right': 1, 'fg_color': '#00ff80'})
		encabezado_azul1 =  wb.add_format({'font_name': 'Arial', 'font_color': 'white', 'bold': 1, 'valign': 'center', 'align': 'center', 'top': 1,
		    'bottom': 1, 'left': 1, 'right': 1, 'fg_color': '#008080'})
		encabezado_azul2 =  wb.add_format({'font_name': 'Arial', 'font_color': 'black', 'bold': 1, 'valign': 'center', 'align': 'center', 'top': 1,
		    'bottom': 1, 'left': 1, 'right': 1, 'fg_color': '#00ffff'})
		encabezado_rojo1 =  wb.add_format({'font_name': 'Arial', 'font_color': 'white', 'bold': 1, 'valign': 'center', 'align': 'center', 'top': 1,
		    'bottom': 1, 'left': 1, 'right': 1, 'fg_color': '#800000'})
		encabezado_rojo2 =  wb.add_format({'font_name': 'Arial', 'font_color': 'black', 'bold': 1, 'valign': 'center', 'align': 'center', 'top': 1,
		    'bottom': 1, 'left': 1, 'right': 1, 'fg_color': '#ff6666'})
		encabezado_morado1 =  wb.add_format({'font_name': 'Arial', 'font_color': 'white', 'bold': 1, 'valign': 'center', 'align': 'center', 'top': 1,
		    'bottom': 1, 'left': 1, 'right': 1, 'fg_color': '#400080'})
		encabezado_morado2 =  wb.add_format({'font_name': 'Arial', 'font_color': 'black', 'bold': 1, 'valign': 'center', 'align': 'center', 'top': 1,
		    'bottom': 1, 'left': 1, 'right': 1, 'fg_color': '#cc66ff'})
		encabezado_rosa =  wb.add_format({'font_name': 'Arial', 'font_color': 'black', 'bold': 1, 'valign': 'center', 'align': 'center', 'top': 1,
		    'bottom': 1, 'left': 1, 'right': 1, 'fg_color': '#e6b9b8'})

		start = datetime.strptime((datetime.now()).strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
		tz = pytz.timezone(user.tz) if user.tz else pytz.utc
		hora = pytz.utc.localize(start).astimezone(tz) """

		request.env.cr.execute('''SELECT cl.ID, cl.NAME, cl.NO_LICITACION, COUNT(*) FROM purchase_order po JOIN crm_lead cl ON po. LEAD_ID = cl.ID 
			WHERE po.TYPE_PURCHASE = 'ins' AND po.STATE not in ('cancel') AND po.MAIL_RECEPTION_CONFIRMED IS True AND po.LEAD_ID = ''' + str(lead) + 
			' GROUP BY 1, 2, 3')
		num = request.env.cr.fetchall()

		request.env.cr.execute('''SELECT (case when UPPER(col5) = 'CANTIDAD' then 'col5' else 'col6' end) cantidad
			FROM crm_input_line ci WHERE ci.id = (select MIN(ID) min_id from crm_input_line ci WHERE ci.lead_id = ''' + str(num[0][0]) + ')')
		min_id = request.env.cr.fetchall()
		cantidad = min_id[0][0]

		col = 3 + num[0][3]
		ws.set_column(0, col, 15)
		fila = 3

		user = request.env['res.users'].sudo().browse(request.env.uid)
		logo = user.company_id.logo
		logo_data = base64.b64decode(logo)
		logo_path = '/tmp/logo.png'
		with open(logo_path, 'wb') as f:
		    f.write(logo_data)

		ws.insert_image('A1:B3', logo_path, {'x_scale': 0.7, 'y_scale': 0.7})
		ws.merge_range(0, 1, 0, col, u'CUADRO COMPARATIVO', encabezado_style)
		ws.merge_range(1, 1, 1, col, u'%s' %num[0][1], encabezado_style)
		ws.merge_range(2, 1, 2, col, u'%s' %num[0][2], encabezado_style)

		supplier_ids = request.env['purchase.order'].search([('state', '=', 'sent'), ('lead_id', '=', num[0][0]), 
			('mail_reception_confirmed', '=', True)]).sorted(key=lambda r: r.name)
		for record in supplier_ids:
			ws.write(fila, 0, u'No. de Cotización', encabezado_style)
			ws.write(fila, 1, u'Proveedor', encabezado_style)
			ws.merge_range(fila, 2, fila, col, record.partner_id.name, style)
			fila += 1

			ws.write(fila, 0, record.name, style_centrado)
			ws.write(fila, 1, u'Total sin IVA', encabezado_style)
			ws.merge_range(fila, 2, fila, col, record.amount_untaxed, style_moneda)
			fila += 1

		fila += 1
		ws.merge_range(fila, 0, fila+1, 1, u'Insumo', encabezado_style)
		ws.merge_range(fila, 2, fila+1, 2, u'Unidad', encabezado_style)
		ws.merge_range(fila, 3, fila+1, 3, u'Cantidad', encabezado_style)
		ws.merge_range(fila, 4, fila, col, 'Precio Unitario', encabezado_style)
		fila += 1
		colr = 4		
		for record in supplier_ids:
			ws.write(fila, colr, record.name, encabezado_style)
			colr += 1
			
		fila += 1
		request.env.cr.execute('SELECT pp.id, pp.product_tmpl_id, round(cil.' + cantidad + '''::numeric, 6) qty, cil.id, MIN(pol.price_unit) 
			FROM crm_lead cl JOIN crm_input_line cil ON cl.ID = cil.LEAD_ID JOIN product_product pp ON cil.input_id = pp.product_tmpl_id
							JOIN purchase_order po ON cl.id = po.lead_id AND po.state = 'sent' AND po.mail_reception_confirmed is true
							JOIN purchase_order_line pol ON po.id = pol.order_id AND pp.id = pol.product_id 
			WHERE cl.id = ''' + str(num[0][0]) + ' GROUP BY 1, 2, 3, 4 ORDER BY pp.DEFAULT_CODE')
		product_ids = request.env.cr.fetchall()
		for record in product_ids:
			product = request.env['product.product'].search([('id', '=', record[0])])
			ws.merge_range(fila, 0, fila, 1, u'[%s] %s' %(product.default_code, product.name), style)
			ws.write(fila, 2, u'%s' %product.uom_id.name.upper(), style_centrado)
			ws.write(fila, 3, u'%s' %record[2], style_numero)
			
			request.env.cr.execute('''SELECT COALESCE(pol.PRICE_UNIT, 0)
				FROM crm_input_line cil JOIN purchase_order po ON cil.lead_id = po.lead_id 
										LEFT JOIN purchase_order_line pol ON po.id = pol.order_id AND pol.product_id = ''' + str(record[0]) +
				' WHERE cil.id = ' + str(record[3]) + " AND po.STATE = 'sent' AND po.MAIL_RECEPTION_CONFIRMED IS True ORDER BY po.name")
			price = request.env.cr.fetchall()
			colr = 4
			for x in price:
				if x[0] == record[4]:
					estilo = style_moneda_negrita
				else:
					estilo = style_moneda
				ws.write(fila, colr, x[0], estilo)
				colr += 1 
			fila += 1

		wb.close()
		content = output.getvalue()
		output.close()

		return request.make_response(content,
		                        [('Content-Type', 'application/octet-stream'),
		                         ('Content-Disposition', 'attachment; filename=Cuadro_comparativo_%s.xlsx;'%(num[0][2]))])