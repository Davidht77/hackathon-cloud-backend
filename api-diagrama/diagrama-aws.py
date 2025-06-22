import json, uuid, os, base64, logging, boto3, requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET_NAME = os.environ["BUCKET_NAME"]
VALIDADOR_FN = "api-diagrama-dev-validarUsuario"       
def pseudocodigo_a_mermaid(pseudocodigo: str) -> str:
    lines       = pseudocodigo.strip().split("\n")
    recursos    = set()
    conexiones  = []

    if lines and lines[0].lower().startswith("diagrama"):
        title_delim = '"' if '"' in lines[0] else "'"
        _title = lines[0].split(title_delim)[1]
        lines  = lines[1:]

    for line in lines:
        line = line.strip()

        if "conectado a" in line:
            try:
                origen_txt, destino_txt  = line.split("conectado a")
                _, origen_nombre         = origen_txt.strip().split(" ", 1)
                _, destino_nombre        = destino_txt.strip().split(" ", 1)
                conexiones.append((
                    origen_nombre.strip('"').strip("'"),
                    destino_nombre.strip('"').strip("'")
                ))
                recursos.update({
                    origen_nombre.strip('"').strip("'"),
                    destino_nombre.strip('"').strip("'")
                })
            except ValueError as e:
                raise ValueError(f"Línea inválida: “{line}” → {e}")
        else:
            try:
                _, nombre = line.split(" ", 1)
                recursos.add(nombre.strip('"').strip("'"))
            except ValueError as e:
                raise ValueError(f"Línea inválida: “{line}” → {e}")

    mermaid = "graph TD\n"
    for r in sorted(recursos):
        mermaid += f'    {r.replace(" ", "_")}[\"{r}\"]\n'
    for orig, dest in conexiones:
        mermaid += f'    {orig.replace(" ", "_")} --> {dest.replace(" ", "_")}\n'
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
        pseudocode = body.get("code")
        if not pseudocode:
            return {"statusCode": 400, "body": json.dumps({"error": "Falta el campo code"})}

        mermaid_code = pseudocodigo_a_mermaid(pseudocode)
        encoded      = base64.urlsafe_b64encode(mermaid_code.encode()).decode()
        img_resp     = requests.get(f"https://mermaid.ink/img/{encoded}", timeout=10)
        if img_resp.status_code != 200:
            return {"statusCode": 502, "body": json.dumps({"error": "Error generando imagen Mermaid"})}

        s3_key = f"{tenant_id}/{user_id}/{uuid.uuid4()}.png"
        s3     = boto3.client("s3")
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

    except Exception as e:
        logger.exception("Fallo interno")
        return {"statusCode": 500, "body": json.dumps({"error": f"Fallo interno: {e}"})} 