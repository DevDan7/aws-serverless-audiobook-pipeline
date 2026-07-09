import os
import json
import urllib.request
import urllib.error
import boto3

# Inicializamos los clientes de AWS
ssm_client = boto3.client('ssm', region_name='us-east-1')
s3_client = boto3.client('s3', region_name='us-east-1')

# Leemos las variables de entorno
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET_NAME')
VOICE_ID = os.environ.get('ELEVENLABS_VOICE_ID')
API_KEY_PARAM_NAME = "/audiobook/dev/elevenlabs_api_key"

def lambda_handler(event, context):
    # 1. Recuperamos la API Key de ElevenLabs de forma segura desde el Parameter Store de AWS
    try:
        print("🔑 Recuperando API Key desde SSM Parameter Store...")
        parameter = ssm_client.get_parameter(Name=API_KEY_PARAM_NAME, WithDecryption=True)
        elevenlabs_api_key = parameter['Parameter']['Value']
    except Exception as e:
        print(f"❌ Error al obtener la API Key de SSM: {e}")
        raise e

    for record in event['Records']:
        try:
            # 2. Parseamos el cuerpo del mensaje de SQS
            body = json.loads(record['body'])
            text_to_process = body.get('text')
            book_id = body.get('book_id')
            page_number = int(body.get('page_number', 1))
            
            print(f"🎙️ Procesando con ElevenLabs: Libro: {book_id} | Página: {page_number}")

            # 3. Llamamos a la API de ElevenLabs usando HTTP nativo de Python (urllib)
            audio_data = sintetizar_voz_elevenlabs(text_to_process, voice_id=VOICE_ID, api_key=elevenlabs_api_key)
            
            if not audio_data:
                raise Exception("La API de ElevenLabs no devolvió datos de audio.")

            # 4. Guardamos el audio binario directamente en S3
            # Usamos el formateador de ceros (:03d) para ordenar alfabéticamente (ej: page_001.mp3)
            s3_key = f"{book_id}/page_{page_number:03d}.mp3"
            
            print(f"💾 Guardando MP3 en S3: {s3_key}...")
            s3_client.put_object(
                Bucket=OUTPUT_BUCKET,
                Key=s3_key,
                Body=audio_data,
                ContentType='audio/mpeg'
            )
            print(f"✅ Página {page_number} completada con éxito.")

        except Exception as e:
            print(f"❌ Error procesando registro SQS: {e}")
            raise e
            
    return {
        'statusCode': 200,
        'body': json.dumps('Procesamiento con ElevenLabs completado')
    }

def sintetizar_voz_elevenlabs(texto, voice_id, api_key):
    """
    Realiza una petición HTTP POST síncrona a la API de ElevenLabs para generar el audio.
    """
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    # Configuramos el modelo multilingüe y los ajustes de voz
    payload = {
        "text": texto,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8
        }
    }
    
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req) as response:
            return response.read() # Devuelve los bytes del archivo MP3
    except urllib.error.HTTPError as e:
        error_content = e.read().decode('utf-8')
        print(f"❌ Error de HTTP en ElevenLabs: {e.code} - {error_content}")
        return None
    except Exception as e:
        print(f"❌ Error de conexión con ElevenLabs: {e}")
        return None