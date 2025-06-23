import os
import boto3
import json

BUCKET_NAME = os.environ["BUCKET_NAME"]

def listar_diagramas(event, context):
    s3 = boto3.client("s3")
    resultados = []

    objetos = s3.list_objects_v2(Bucket=BUCKET_NAME).get("Contents", [])

    for obj in objetos:
        key = obj["Key"]
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": key},
            ExpiresIn=3600
        )
        resultados.append(url)

    return {
        "statusCode": 200,
        "body": json.dumps(resultados),
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type,Authorization"
        }
    }
