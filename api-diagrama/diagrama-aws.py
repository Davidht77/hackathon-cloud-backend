import boto3
import json
import uuid
import os
from diagrams import Diagram
from diagrams.aws.compute import Lambda as AWSLambda
from diagrams.aws.storage import S3 as AWSS3
from diagrams.aws.database import Dynamodb as AWSDynamoDB
from datetime import datetime
from zoneinfo import ZoneInfo

BUCKET_NAME = os.environ["BUCKET_NAME"]

def pseudocodigo_a_diagrams(pseudocodigo: str, filename: str = "output"):
    lines = pseudocodigo.strip().split("\n")
    title = "Diagrama"
    recursos = {}
    conexiones = []

    if lines[0].lower().startswith("diagrama"):
        title = lines[0].split('"')[1].strip()
        lines = lines[1:]

    for line in lines:
        line = line.strip()
        if "conectado a" in line:
            origen_txt, destino_txt = line.split("conectado a")
            origen_tipo, origen_nombre = origen_txt.strip().split(" ", 1)
            destino_tipo, destino_nombre = destino_txt.strip().split(" ", 1)
            conexiones.append(((origen_tipo, origen_nombre.strip('"')), (destino_tipo, destino_nombre.strip('"'))))
        else:
            tipo, nombre = line.strip().split(" ", 1)
            recursos[(tipo, nombre.strip('"'))] = None

    imports = [
        "from diagrams import Diagram",
        "from diagrams.aws.compute import Lambda as AWSLambda",
        "from diagrams.aws.storage import S3 as AWSS3",
        "from diagrams.aws.database import Dynamodb as AWSDynamoDB"
    ]

    code = "\n".join(imports) + f"\n\nwith Diagram('{title}', show=False, filename='{filename}'):\n"

    for (tipo, nombre) in recursos.keys():
        var_name = nombre.replace(" ", "_").lower()
        recursos[(tipo, nombre)] = var_name
        clase = f"AWS{tipo}" if tipo in ["S3", "Lambda", "DynamoDB"] else tipo
        code += f"    {var_name} = {clase}(\"{nombre}\")\n"

    for (origen, destino) in conexiones:
        var_o = recursos[origen]
        var_d = recursos[destino]
        code += f"    {var_o} >> {var_d}\n"

    return code

def lambda_handler(event, context):
    try:
        body = json.loads(event['body'])
        pseudocode = body.get('code')
        if not pseudocode:
            return {"statusCode": 400, "body": json.dumps({"error": "Pseudocódigo requerido"})}

        tenant_id = event['requestContext']['authorizer']['tenant_id']
        user_id = event['requestContext']['authorizer']['user_id']

        output_name = f"{uuid.uuid4()}"
        output_path = f"/tmp/{output_name}"

        code = pseudocodigo_a_diagrams(pseudocode, filename=output_path)

        exec_env = {
            "__builtins__": __builtins__,
            "Diagram": Diagram,
            "AWSLambda": AWSLambda,
            "AWSS3": AWSS3,
            "AWSDynamoDB": AWSDynamoDB
        }

        exec(code, exec_env)

        file_path = output_path + ".png"
        if not os.path.exists(file_path):
            return {"statusCode": 500, "body": json.dumps({"error": "Error al generar el diagrama"})}

        s3_key = f"{tenant_id}/{user_id}/{output_name}.png"
        s3 = boto3.client('s3')
        s3.upload_file(file_path, BUCKET_NAME, s3_key)

        url = s3.generate_presigned_url('get_object', Params={
            'Bucket': BUCKET_NAME,
            'Key': s3_key
        }, ExpiresIn=3600)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Diagrama generado con éxito",
                "diagram_url": url
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Fallo interno: {str(e)}"})
        }
