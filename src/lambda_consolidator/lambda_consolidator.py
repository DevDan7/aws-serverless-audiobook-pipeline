import os
import json
import boto3

# Inicializamos los clientes de AWS
s3_client = boto3.client('s3')
sns_client = boto3.client('sns')
dynamodb = boto3.resource('dynamodb')

DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE')
FINAL_BUCKET = os.environ.get('FINAL_BUCKET_NAME')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

def lambda_handler(event, context):
    # 1. Extraemos los detalles del archivo MP3 creado
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    file_key = event['Records'][0]['s3']['object']['key']
    
    # Si por alguna razón el archivo no es un MP3 o no está en la carpeta de un libro, ignoramos
    if "/" not in file_key or not file_key.endswith(".mp3"):
        return {"statusCode": 200, "body": "Archivo no elegible para consolidación"}

    # Ejemplo de file_key: "libro_mindset/page_001.mp3" (o page_001.1234.mp3 si es Polly)
    book_id = file_key.split('/')[0]
    print(f"📁 Detectada nueva página para el Libro: {book_id}")

    # 2. Incrementamos Atómicamente el contador en DynamoDB y obtenemos el estado actualizado
    table = dynamodb.Table(DYNAMODB_TABLE)
    try:
        response = table.update_item(
            Key={'BookID': book_id},
            UpdateExpression="SET ProcessedPages = ProcessedPages + :val",
            ExpressionAttributeValues={':val': 1},
            ReturnValues="ALL_NEW" # Nos devuelve cómo quedó el ítem después de sumar
        )
    except Exception as e:
        print(f"⚠️ Error al actualizar DynamoDB. ¿Aún no se registra este libro?: {e}")
        return {"statusCode": 200, "body": "Ignorando actualización huérfana"}

    item = response['Attributes']
    processed_pages = int(item['ProcessedPages'])
    total_pages = int(item['TotalPages'])
    status = item['Status']

    print(f"📊 Estado actual del libro {book_id}: {processed_pages} de {total_pages} páginas completadas.")

    # 3. ¿Llegamos al final del libro?
    if processed_pages == total_pages and status != 'COMPLETED':
        print(f"🎉 ¡ÚLTIMA PÁGINA RECIBIDA! Iniciando consolidación del libro {book_id}...")
        
        # Marcamos la base de datos como "CONSOLIDATING" para evitar que otra ejecución paralela intente lo mismo
        table.update_item(
            Key={'BookID': book_id},
            UpdateExpression="SET #st = :status",
            ExpressionAttributeNames={'#st': 'Status'},
            ExpressionAttributeValues={':status': 'CONSOLIDATING'}
        )

        try:
            # 4. Listamos todos los fragmentos MP3 del libro en S3
            s3_response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=f"{book_id}/")
            objects = s3_response.get('Contents', [])
            
            # Filtramos solo archivos MP3 y los ordenamos alfabéticamente (gracias al zero-padding)
            mp3_objects = sorted(
                [obj for obj in objects if obj['Key'].endswith('.mp3')],
                key=lambda x: x['Key']
            )

            print(f"🔗 Uniendo {len(mp3_objects)} archivos MP3 de forma binaria...")
            final_audio_bytes = bytearray()

            # 5. Descargamos los binarios de cada página y los concatenamos en memoria
            for obj in mp3_objects:
                key_to_download = obj['Key']
                print(f"⏬ Descargando fragmento: {key_to_download}")
                audio_part = s3_client.get_object(Bucket=bucket_name, Key=key_to_download)
                final_audio_bytes.extend(audio_part['Body'].read())

            # 6. Guardamos el audiolibro unificado en el TERCER bucket (el final)
            final_key = f"{book_id}.mp3"
            print(f"📤 Guardando audiolibro final en S3: {FINAL_BUCKET}/{final_key}...")
            s3_client.put_object(
                Bucket=FINAL_BUCKET,
                Key=final_key,
                Body=bytes(final_audio_bytes),
                ContentType='audio/mpeg'
            )

            # 7. Actualizamos el estado en DynamoDB a COMPLETED
            table.update_item(
                Key={'BookID': book_id},
                UpdateExpression="SET #st = :status",
                ExpressionAttributeNames={'#st': 'Status'},
                ExpressionAttributeValues={':status': 'COMPLETED'}
            )
            print(f"🏆 ¡Libro {book_id} completado con éxito en DynamoDB!")

            # 8. Notificamos al usuario por Amazon SNS
            mensaje_notificacion = f"""¡Tu audiolibro está listo! 🎧📚
            
El libro '{book_id}' ha sido completamente procesado y consolidado con éxito.
Puedes descargarlo ahora mismo desde tu bucket final en S3:
Bucket: {FINAL_BUCKET}
Archivo: {final_key}

¡Gracias por usar tu plataforma de Cloud Audiobook Generator!
"""
            sns_client.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f"🔔 Audiolibro Listo: {book_id}",
                Message=mensaje_notificacion
            )
            print("✉️ Correo de notificación enviado por SNS.")

        except Exception as e:
            print(f"❌ Error catastrófico en la consolidación: {e}")
            table.update_item(
                Key={'BookID': book_id},
                UpdateExpression="SET #st = :status",
                ExpressionAttributeNames={'#st': 'Status'},
                ExpressionAttributeValues={':status': 'ERROR'}
            )
            raise e

    return {
        'statusCode': 200,
        'body': json.dumps('Proceso de consolidación concluido')
    }