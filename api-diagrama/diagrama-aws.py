import json, uuid, os, base64, logging, boto3, requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET_NAME  = os.environ["BUCKET_NAME"]
VALIDADOR_FN = "api-diagrama-dev-validarUsuario"

# ───────────────────────────────
# Cabeceras CORS (ajusta el Origin)
# ───────────────────────────────
CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",           # ← o "http://localhost:5173"
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "OPTIONS,POST"
}

# ───────────────────────────────
# Pseudocódigo → Mermaid
# ───────────────────────────────
def pseudocodigo_a_mermaid(pseudocodigo: str) -> str:
    # … (tu mismo código sin cambios) …
    return mermaid


def lambda_handler(event, _context):
    try:
        logger.info("Evento: %s", json.dumps(event))

        # ───────── 1) Manejar pre-flight OPTIONS ─────────
        if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
            return {
                "statusCode": 200,
                "headers": CORS_HEADERS,
                "body": json.dumps({"message": "Pre-flight OK"})
            }

        # ───────── 2) Validar token ─────────
        token = (event.get("headers", {}) or {}).get("Authorization")
        if not token:
            return {
                "statusCode": 401,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Token no proporcionado"})
            }

        lambda_cli = boto3.client("lambda")
        resp = lambda_cli.invoke(
            FunctionName  = VALIDADOR_FN,
            InvocationType= "RequestResponse",
            Payload       = json.dumps({"token": token})
        )
        validation = json.loads(resp["Payload"].read())
        if validation.get("statusCode", 403) == 403:
            return {
                "statusCode": 403,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Token inválido"})
            }

        user      = json.loads(validation["body"])
        tenant_id = user["tenant_id"]
        user_id   = user["user_id"]

        # ───────── 3) Leer body ─────────
        body        = json.loads(event.get("body") or "{}")
        pseudocode  = body.get("code")
        if not pseudocode:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Falta el campo code"})
            }

        # ───────── 4) Generar imagen Mermaid ─────────
        mermaid_code = pseudocodigo_a_mermaid(pseudocode)
        encoded      = base64.urlsafe_b64encode(mermaid_code.encode()).decode()
        img_resp     = requests.get(f"https://mermaid.ink/img/{encoded}", timeout=10)
        if img_resp.status_code != 200:
            return {
                "statusCode": 502,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Error generando imagen Mermaid"})
            }

        # ───────── 5) Guardar PNG en S3 ─────────
        s3_key = f"{tenant_id}/{user_id}/{uuid.uuid4()}.png"
        s3     = boto3.client("s3")
        s3.put_object(
            Bucket      = BUCKET_NAME,
            Key         = s3_key,
            Body        = img_resp.content,
            ContentType = "image/png"
        )

        url_firmada = s3.generate_presigned_url(
            ClientMethod = "get_object",
            Params       = {"Bucket": BUCKET_NAME, "Key": s3_key},
            ExpiresIn    = 3600
        )

        # ───────── 6) Éxito (201 CREATED) ─────────
        return {
            "statusCode": 201,
            "headers": CORS_HEADERS,
            "body": json.dumps({
                "message":      "Diagrama generado con éxito",
                "diagram_url":  url_firmada,
                "tenant_id":    tenant_id,
                "user_id":      user_id
            })
        }

    except Exception as e:
        logger.exception("Fallo interno")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": f"Fallo interno: {e}"})
        }
