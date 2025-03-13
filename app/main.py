from flask import Flask, jsonify, request
from dotenv import load_dotenv
import os
import xmlrpc.client

load_dotenv()

app = Flask(__name__)

ODOO_URL = os.getenv('ODOO_URL')
ODOO_DB = os.getenv('ODOO_DB')
ODOO_USER = os.getenv('ODOO_USER')
ODOO_PASSWORD = os.getenv('ODOO_PASSWORD')

if not ODOO_URL.startswith(('http://', 'https://')):
    raise ValueError('La variable ODOO_URL debe iniciar explícitamente con http:// o https://')

common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
# TODO Crear excepción para la conexión errónea

def obtener_datos_compras(mes=None, anio=None, company_id=None):

    domain = []
    if mes and anio:
        fecha_inicio = f"{anio}-{mes.zfill(2)}-01"
        fecha_fin = f"{anio}-{mes.zfill(2)}-31"
        domain.append(('date_order', '>=', fecha_inicio))
        domain.append(('date_order', '<=', fecha_fin))

    if company_id:
        domain.append(('company_id', '=', int(company_id)))

    compras = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'purchase.order', 'search_read',
        [domain],
        {'fields': ['company_id', 'id', 'name', 'partner_id', 'currency_id', 'amount_untaxed', 'amount_tax']}
    )

    resultado = []
    for compra in compras:
        orden_name = compra['name']

        facturas = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'account.move', 'search_read',
            [[
                ['invoice_origin', '=', orden_name],
                ['move_type', '=', 'in_invoice'],
                ['state', '=', 'posted']
            ]],
            {'fields': ['amount_total', 'amount_residual']}
        )

        resultado.append({
            'company_id': compra['company_id'],
            'orden': compra['id'],
            'proveedor': compra['partner_id'][1],
            'moneda': compra['currency_id'][1],
            'subtotal': compra['amount_untaxed'],
            'impuestos': compra['amount_tax'],
            'monto_total_solicitado': compra['amount_untaxed'] + compra['amount_tax'],
            'numero_de_facturas': len(facturas),
            'monto_facturado': sum(f['amount_total'] for f in facturas),
            'saldo': sum(f['amount_residual'] for f in facturas)
        })

    return resultado


@app.route('/api/compras', methods=['GET'])
def api_compras():
    mes = request.args.get('mes')
    anio = request.args.get('anio')
    company_id = request.args.get('company_id')

    data = obtener_datos_compras(mes, anio, company_id)
    return jsonify(data)


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'running'}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')