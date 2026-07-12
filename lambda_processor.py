import os
import json
import boto3

s3_client = boto3.client('s3')
polly_client = boto3.client('polly')

# Cambia el nombre del bucket de salida por la variable de entorno correspondiente en tu Terraform
OUTPUT_BUCKET = os.environ['OUTPUT_BUCKET_NAME']

def lambda_handler(event, context):
    for record in event['Records']:
        # SQS envía el mensaje dentro del campo 'body'
        message_body = json.loads(record['body'])
        
        book_id = message_body['BookID']
        page_num = message_body['PageNum']
        total_pages = message_body['TotalPages']
        text = message_body['Text']
        
        # Formatear el nombre de la página para asegurar orden lexicográfico (ej. page_001.mp3)
        page_str = str(page_num).zfill(3)
        output_key = f"{book_id}/page_{page_str}.mp3"
        
        print(f"Procesando {book_id} - Página {page_num}/{total_pages} con Amazon Polly...")
        
        try:
            # Llamada a Amazon Polly usando motor Neural y voz
            response = polly_client.synthesize_speech(
                Engine='neural',
                LanguageCode='pt-BR',
                OutputFormat='mp3',
                Text=text,
                VoiceId='Thiago'
            )
            
            # Leer el stream de audio retornado por Polly
            audio_stream = response['AudioStream'].read()
            
            # Guardar el fragmento MP3 directamente en S3 de salidas intermedias
            s3_client.put_object(
                Bucket=OUTPUT_BUCKET,
                Key=output_key,
                Body=audio_stream,
                ContentType='audio/mpeg'
            )
            
            print(f"Guardado exitoso en S3: {output_key}")
            
        except Exception as e:
            print(f"Error procesando síntesis de voz para {book_id} - pág {page_num}: {str(e)}")
            raise e # Al lanzar la excepción, SQS enviará el mensaje a la DLQ tras los reintentos configurados

    return {
        "statusCode": 200,
        "body": json.dumps("Procesamiento de página completado con Polly.")
    }