import boto3
import hashlib
import json

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def lambda_handler(event, context):
    try:
        body = json.loads(event['body'])

        tenant_id = body['tenant_id']
        user_id = body['email']
        password = body['password']

        dynamodb = boto3.resource('dynamodb')
        t_usuarios = dynamodb.Table('t_usuarios3')  

        response = t_usuarios.get_item(Key={
            'tenant_id': tenant_id,
            'user_id': user_id
        })

        if 'Item' in response:
            return {
                'statusCode': 409,
                'body': json.dumps({
                    'error': 'El usuario ya existe en este tenant'
                })
            }

        hashed_password = hash_password(password)

        t_usuarios.put_item(Item={
            'tenant_id': tenant_id,
            'user_id': user_id,
            'password': hashed_password,
        })

        return {
            'statusCode': 201,
            'body': json.dumps({
                'message': 'Usuario registrado exitosamente',
                'tenant_id': tenant_id,
                'user_id': user_id
            })
        }

    except Exception as e:
        print("ERROR:", str(e))
        return {
            'statusCode': 500,
            'body': json.dumps({ "error": str(e) })
        }