import json, uuid, os, base64, logging, boto3, requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET_NAME = os.environ["BUCKET_NAME"]
VALIDADOR_FN = "api-diagrama-dev-validarUsuario"

def json_a_mermaid(data: dict) -> str:
    nodos = data.get("nodos", [])
    conexiones = data.get("conexiones", [])

    if not nodos:
        raise ValueError("El JSON debe contener una lista de 'nodos'.")

    mermaid = "graph TD\n"
    for nodo in nodos:
        id_nodo = nodo.get("id")
        etiqueta = nodo.get("etiqueta", id_nodo)
        if not id_nodo:
            raise ValueError("Cada nodo debe tener un 'id'.")
        mermaid += f'    {id_nodo}["{etiqueta}"]\n'

    for conexion in conexiones:
        origen = conexion.get("origen")
        destino = conexion.get("destino")
        if not origen or not destino:
            raise ValueError("Cada conexión debe tener 'origen' y 'destino'.")
        mermaid += f'    {origen} --> {destino}\n'

    return mermaid


def lambda_handler(event, _context):
    try:
        logger.info("Evento: %s", json.dumps(event))

        token = (event.get("headers", {}) or {}).get("Authorization")
        if not token:
            return {"statusCode": 401, "body": json.dumps({"error": "Token no proporcionado"})}

        lambda_cli = boto3.client("lambda")
        resp = lambda_cli.invoke(
            FunctionName=VALIDADOR_FN,
            InvocationType="RequestResponse",
            Payload=json.dumps({"token": token})
        )
        validation = json.loads(resp["Payload"].read())
        if validation.get("statusCode", 403) == 403:
            return {"statusCode": 403, "body": json.dumps({"error": "Token inválido"})}

        user = json.loads(validation["body"])
        tenant_id, user_id = user["tenant_id"], user["user_id"]

        body = json.loads(event.get("body") or "{}")
        logger.info("Body recibido: %s", body)
        json_data = body.get("code")
        logger.info("JSON Data para Mermaid: %s", json_data)
        if not json_data:
            return {"statusCode": 400, "body": json.dumps({"error": "Falta el campo code con el JSON"})}

        mermaid_code = json_a_mermaid(json_data)
        encoded = base64.urlsafe_b64encode(mermaid_code.encode()).decode()
        img_resp = requests.get(f"https://mermaid.ink/img/{encoded}", timeout=10)
        if img_resp.status_code != 200:
            return {"statusCode": 502, "body": json.dumps({"error": "Error generando imagen Mermaid"})}

        s3_key = f"{tenant_id}/{user_id}/{uuid.uuid4()}.png"
        s3 = boto3.client("s3")
        s3.put_object(Bucket=BUCKET_NAME, Key=s3_key, Body=img_resp.content, ContentType="image/png")

        url_firmada = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": BUCKET_NAME, "Key": s3_key},
            ExpiresIn=3600
        )

        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Allow-Methods": "OPTIONS,POST",
            },
            "body": json.dumps({"message": "Diagrama generado con éxito", "diagram_url": url_firmada})
        }

    except ValueError as ve:
        logger.warning(f"Error de validación: {ve}")
        return {"statusCode": 400, "body": json.dumps({"error": str(ve)})}
    except Exception as e:
        logger.exception("Fallo interno")
        return {"statusCode": 500, "body": json.dumps({"error": f"Fallo interno: {e}"})}