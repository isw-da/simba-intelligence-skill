import sys
sys.path.insert(0, '/opt/zoomdata/lib/python')
import json
import ssl

TENANT = "ly98km3k7dygnl9.uk.qlikcloud.com"
APP_ID = "c5aab8b9-eeec-46b5-87cc-af63ff080f12"
API_KEY = "eyJhbGciOiJFUzM4NCIsImtpZCI6ImJlYzFmYzk2LTM0ZDAtNDVlZi1hZWNhLTU1ZGY5NmExMWE1NiIsInR5cCI6IkpXVCJ9.eyJzdWJUeXBlIjoidXNlciIsInRlbmFudElkIjoiUWtKeGFhYjROejRwbFFONUZQUENzb3VrbFhjRlBDYUgiLCJqdGkiOiJiZWMxZmM5Ni0zNGQwLTQ1ZWYtYWVjYS01NWRmOTZhMTFhNTYiLCJhdWQiOiJxbGlrLmFwaSIsImlzcyI6InFsaWsuYXBpL2FwaS1rZXlzIiwic3ViIjoiNjk5ZGVjZjA3MmQxNjQwY2MyOWQ4NzgxIn0.tZvM_67_YtiIO7nSI55UIHRS32hHdJ8Z2ESx-5Zj92j3rIWPKoDOrz_sqk-b8oMoDFBzY1CoImfThRNmT-jO-4kj74uDrKu2ZcKU6ZNp78NNuot6F5_mWD8vdk3sZGEy"

def _connect_to_qlik():
    import websocket
    ws_url = f"wss://{TENANT}/app/{APP_ID}"
    headers = [f"Authorization: Bearer {API_KEY}"]
    ws = websocket.create_connection(ws_url, header=headers, sslopt={"cert_reqs": ssl.CERT_NONE})
    msg_id = 0
    def send_msg(method, handle, params):
        nonlocal msg_id
        msg_id += 1
        payload = {"jsonrpc": "2.0", "id": msg_id, "handle": handle, "method": method, "params": params}
        ws.send(json.dumps(payload))
        while True:
            resp = json.loads(ws.recv())
            if resp.get("id") == msg_id:
                return resp
    result = send_msg("OpenDoc", -1, [APP_ID])
    doc_handle = result["result"]["qReturn"]["qHandle"]
    return ws, doc_handle, send_msg

def _fetch_hypercube(ws, doc_handle, send_msg, dimensions, measures):
    dim_defs = [{"qDef": {"qFieldDefs": [d]}} for d in dimensions]
    msr_defs = [{"qDef": {"qDef": m[0], "qLabel": m[1]}} for m in measures]
    hc = {
        "qInfo": {"qType": "export"},
        "qHyperCubeDef": {
            "qDimensions": dim_defs,
            "qMeasures": msr_defs,
            "qInitialDataFetch": [{"qLeft": 0, "qTop": 0, "qWidth": len(dimensions) + len(measures), "qHeight": 1000}]
        }
    }
    result = send_msg("CreateSessionObject", doc_handle, [hc])
    obj_handle = result["result"]["qReturn"]["qHandle"]
    result = send_msg("GetLayout", obj_handle, [])
    cube = result["result"]["qLayout"]["qHyperCube"]
    records = []
    all_labels = dimensions + [m[1] for m in measures]
    for page in cube["qDataPages"]:
        for row in page["qMatrix"]:
            record = {}
            for i, label in enumerate(all_labels):
                cell = row[i]
                if i < len(dimensions):
                    record[label] = cell.get("qText", "")
                else:
                    record[label] = cell.get("qNum", 0) if cell.get("qNum") is not None else 0
            records.append(record)
    return records


def flint_order_delivery(limit=None, fields=None):
    """Flint Group order and delivery performance - includes customer, product, OTIF metrics, revenue, and delivery status for Q4 2025."""
    ws, doc_handle, send_msg = _connect_to_qlik()

    dimensions = [
        "CustomerName", "AccountManager", "Segment", "Country", "Region",
        "ProductName", "ProductGroup", "ProductLine",
        "OrderID", "OrderDate", "RequestedDeliveryDate",
        "ActualDeliveryDate", "DeliveryStatus"
    ]

    measures = [
        ("Sum(OrderQtyKG)", "OrderQtyKG"),
        ("Sum(NetPriceEUR)", "NetPriceEUR"),
        ("Sum(DeliveredQtyKG)", "DeliveredQtyKG"),
        ("If(ActualDeliveryDate <= RequestedDeliveryDate, 'Yes', 'No')", "OnTime"),
        ("If(DeliveredQtyKG >= OrderQtyKG, 'Yes', 'No')", "InFull"),
        ("If(ActualDeliveryDate <= RequestedDeliveryDate AND DeliveredQtyKG >= OrderQtyKG, 'Yes', 'No')", "OTIF"),
        ("Date(RequestedDeliveryDate, 'YYYY-MM') ", "DeliveryMonth"),
    ]

    records = _fetch_hypercube(ws, doc_handle, send_msg, dimensions, measures)
    ws.close()

    if limit:
        records = records[:limit]
    return records


def flint_customer_summary(limit=None, fields=None):
    """Flint Group customer-level summary with total revenue, order count, OTIF rate, and average order value for Q4 2025. Use this for account reviews and QBR preparation."""
    ws, doc_handle, send_msg = _connect_to_qlik()

    dimensions = [
        "CustomerName", "AccountManager", "Segment", "Country", "Region"
    ]

    measures = [
        ("Count(DISTINCT OrderID)", "TotalOrders"),
        ("Sum(NetPriceEUR)", "TotalRevenueEUR"),
        ("Sum(NetPriceEUR) / Count(DISTINCT OrderID)", "AvgOrderValueEUR"),
        ("Sum(OrderQtyKG)", "TotalOrderedKG"),
        ("Sum(DeliveredQtyKG)", "TotalDeliveredKG"),
        ("Count(DISTINCT {$<DeliveryStatus={'Partial'}>} OrderID)", "PartialDeliveries"),
        ("Sum(If(ActualDeliveryDate <= RequestedDeliveryDate, 1, 0)) / Count(OrderID)", "OnTimeRate"),
        ("Sum(If(DeliveredQtyKG >= OrderQtyKG, 1, 0)) / Count(OrderID)", "InFullRate"),
        ("Sum(If(ActualDeliveryDate <= RequestedDeliveryDate AND DeliveredQtyKG >= OrderQtyKG, 1, 0)) / Count(OrderID)", "OTIFRate"),
    ]

    records = _fetch_hypercube(ws, doc_handle, send_msg, dimensions, measures)

    for r in records:
        r["OnTimeRate_Pct"] = round(r.get("OnTimeRate", 0) * 100, 1)
        r["InFullRate_Pct"] = round(r.get("InFullRate", 0) * 100, 1)
        r["OTIFRate_Pct"] = round(r.get("OTIFRate", 0) * 100, 1)
        r["AvgOrderValueEUR"] = round(r.get("AvgOrderValueEUR", 0), 0)
        del r["OnTimeRate"]
        del r["InFullRate"]
        del r["OTIFRate"]

    ws.close()
    if limit:
        records = records[:limit]
    return records


def flint_product_mix(limit=None, fields=None):
    """Flint Group product performance by customer - shows which products each customer buys, quantities, and revenue. Use for cross-sell and upsell analysis."""
    ws, doc_handle, send_msg = _connect_to_qlik()

    dimensions = [
        "CustomerName", "ProductName", "ProductGroup", "ProductLine"
    ]

    measures = [
        ("Count(DISTINCT OrderID)", "Orders"),
        ("Sum(OrderQtyKG)", "TotalKG"),
        ("Sum(NetPriceEUR)", "RevenueEUR"),
        ("Sum(NetPriceEUR) / Sum(OrderQtyKG)", "PricePerKG"),
    ]

    records = _fetch_hypercube(ws, doc_handle, send_msg, dimensions, measures)
    for r in records:
        r["PricePerKG"] = round(r.get("PricePerKG", 0), 2)
    ws.close()
    if limit:
        records = records[:limit]
    return records
