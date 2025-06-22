import boto3
import json
from datetime import datetime
from zoneinfo import ZoneInfo 
import os

def lambda_handler(event, context):
    try:
        if isinstance(event, dict) and 'token' in event:
            body = event
        elif isinstance(event, dict) and 'body' in event:
            body = json.loads(event['body'])
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Formato inválido de entrada'})
            }

        token = body['token']
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Error al procesar entrada: {str(e)}'})
        }

    dynamodb = boto3.resource('dynamodb')
    t_tokens = dynamodb.Table(os.environ['TABLE_TOKENS'])
    t_usuarios = dynamodb.Table(os.environ['TABLE_USUARIOS'])

    # Buscar el token en la tabla
    response = t_tokens.get_item(Key={'token': token})
    if 'Item' not in response:
        return {
            'statusCode': 403,
            'body': json.dumps({'error': 'Token no existe'})
        }

    token_data = response['Item']
    expires = token_data['expires']
    tenant_id = token_data['tenant_id']
    user_id = token_data['user_id']  # Este es el email

    # Validar que no haya expirado
    now = datetime.now(ZoneInfo("America/Lima")).strftime('%Y-%m-%d %H:%M:%S')
    if now > expires:
        return {
            'statusCode': 403,
            'body': json.dumps({'error': 'Token expirado'})
        }

    # Verificar que el usuario todavía exista
    response_user = t_usuarios.get_item(Key={
        'tenant_id': tenant_id,
        'user_id': user_id
    })

    if 'Item' not in response_user:
        return {
            'statusCode': 403,
            'body': json.dumps({'error': 'Usuario no encontrado'})
        }

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Token válido',
            'tenant_id': tenant_id,
            'user_id': user_id,
            'expires': expires
        })
    }