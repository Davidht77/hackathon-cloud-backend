import json, uuid, os, base64, logging, boto3, requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET_NAME  = os.environ["BUCKET_NAME"]
VALIDADOR_FN = "api-diagrama-dev-validarUsuario"

CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",           restringir
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "OPTIONS,POST"
}

def pseudocodigo_a_mermaid(pseudocodigo: str) -> str:
    lines = pseudocodigo.strip().split("\n")
    if not lines:
        raise ValueError("Pseudocódigo vacío")

    header = lines[0].lower()
    if header.startswith("erdiagrama"):
        tipo = "erDiagram"
        lines = lines[1:]
    elif header.startswith("diagrama"):
        tipo = "graph TD"
        lines = lines[1:]
    else:
        tipo = "graph TD"

    if tipo == "erDiagram":
        entidades  = {}
        relaciones = []

        for raw in lines:
            line = raw.strip()
            if not line:
                continue

            if "{" in line and "}" in line:
                entidad, bloque   = line.split("{", 1)
                entidad           = entidad.strip()
                atributos_raw     = bloque.rstrip("}").strip()
                atributos         = atributos_raw.split("string")
                entidades[entidad] = [
                    "string " + a.strip()
                    for a in atributos
                    if a.strip()
                ]

            elif any(sym in line for sym in ["||--", "}o--", "o{", "}o--o{"]):
                relaciones.append(line)

            else:
                raise ValueError(f"Línea ER inválida: “{line}”")

        mermaid = "erDiagram\n"
        for entidad, attrs in entidades.items():
            mermaid += f"    {entidad} {{\n"
            for attr in attrs:
                mermaid += f"        {attr}\n"
            mermaid += "    }\n"
        for rel in relaciones:
            mermaid += f"    {rel}\n"
        return mermaid

    recursos   = set()
    conexiones = []

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        if "conectado a" in line:
            try:
                origen_txt, destino_txt = line.split("conectado a")
                _, origen_nombre  = origen_txt.strip().split(" ", 1)
                _, destino_nombre = destino_txt.strip().split(" ", 1)
                origen  = origen_nombre.strip(' "\'')
                destino = destino_nombre.strip(' "\'')
                conexiones.append((origen, destino))
                recursos.update([origen, destino])
            except ValueError as e:
                raise ValueError(f"Línea inválida: “{line}” → {e}")
        else:
            try:
                _, nombre = line.split(" ", 1)
                recursos.add(nombre.strip(' "\''))
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

        if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
            return {
                "statusCode": 200,
                "headers": CORS_HEADERS,
                "body": json.dumps({"message": "Pre-flight OK"})
            }

        token = (event.get("headers") or {}).get("Authorization")
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
        if validation.get("statusCode") == 403:
            return {
                "statusCode": 403,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Token inválido"})
            }

        user         = json.loads(validation["body"])
        tenant_id    = user["tenant_id"]
        user_id      = user["user_id"]

        body        = json.loads(event.get("body") or "{}")
        pseudocode  = body.get("code")
        if not pseudocode:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Falta el campo code"})
            }

        mermaid_code = pseudocodigo_a_mermaid(pseudocode)
        encoded      = base64.urlsafe_b64encode(mermaid_code.encode()).decode()
        img_resp     = requests.get(f"https://mermaid.ink/img/{encoded}", timeout=10)
        if img_resp.status_code != 200:
            return {
                "statusCode": 502,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Error generando imagen Mermaid"})
            }

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

        return {
            "statusCode": 201,                
            "headers": CORS_HEADERS,
            "body": json.dumps({
                "message":     "Diagrama generado con éxito",
                "diagram_url": url_firmada,
                "tenant_id":   tenant_id,
                "user_id":     user_id
            })
        }

    except Exception as e:
        logger.exception("Fallo interno")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": f"Fallo interno: {e}"})
        }