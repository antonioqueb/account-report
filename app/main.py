from flask import Flask, jsonify
from dotenv import load_dotenv
import os
import xmlrpc.client

load_dotenv()

app = Flask(__name__)

ODOO_URL = os.getenv('ODOO_URL')
ODOO_DB = os.getenv('ODOO_DB')
ODOO_USER = os.getenv('ODOO_USER')
ODOO_PASSWORD = os.getenv('ODOO_PASSWORD')

# Validar protocolo explícito en la URL
if not ODOO_URL.startswith(('http://', 'https://')):
    raise ValueError('La variable ODOO_URL debe iniciar explícitamente con http:// o https://')

common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')


def obtener_datos_compras():
    compras = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'purchase.order', 'search_read', [],
        {'fields': ['id', 'partner_id', 'currency_id', 'amount_untaxed', 'amount_tax']}
    )

    resultado = []
    for compra in compras:
        orden_id = compra['id']

        facturas = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'account.move', 'search_read',
            [[['invoice_origin', 'ilike', f'PO{orden_id}'], ['move_type', '=', 'in_invoice'], ['state', '=', 'posted']]],
            {'fields': ['amount_total']}
        )

        num_facturas = len(facturas)
        monto_facturado = sum(factura['amount_total'] for factura in facturas)
        monto_solicitado = compra['amount_untaxed'] + compra['amount_tax']
        saldo = monto_solicitado - monto_facturado

        resultado.append({
            'orden': orden_id,
            'proveedor': compra['partner_id'][1],
            'moneda': compra['currency_id'][1],
            'subtotal': compra['amount_untaxed'],
            'impuestos': compra['amount_tax'],
            'monto_total_solicitado': monto_solicitado,
            'numero_de_facturas': num_facturas,
            'monto_facturado': monto_facturado,
            'saldo': saldo
        })

    return resultado


@app.route('/api/compras', methods=['GET'])
def api_compras():
    data = obtener_datos_compras()
    return jsonify(data)


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'running'}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')