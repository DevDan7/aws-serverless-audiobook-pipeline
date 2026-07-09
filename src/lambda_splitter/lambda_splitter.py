import os
import json
import boto3
from pypdf import PdfReader

s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')

SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE')

def lambda_handler(event, context):
    # 1. Extraemos los datos del evento de S3
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    file_key = event['Records'][0]['s3']['object']['key']
    
    # El ID del libro será el nombre del archivo (limpiando espacios y caracteres)
    book_id = os.path.splitext(file_key)[0].replace(" ", "_")
    local_pdf_path = f"/tmp/{file_key}"
    
    print(f"📥 Descargando {file_key} de S3...")
    
    try:
        # 2. Descargamos el archivo PDF temporalmente a la Lambda
        s3_client.download_file(bucket_name, file_key, local_pdf_path)
        
        # 3. Leemos el PDF con pypdf
        reader = PdfReader(local_pdf_path)
        total_pages = len(reader.pages)
        print(f"📖 PDF detectado: {total_pages} páginas.")
        
        # 4. Registramos el inicio del libro en DynamoDB
        table = dynamodb.Table(DYNAMODB_TABLE)
        table.put_item(
            Item={
                'BookID': book_id,
                'TotalPages': total_pages,
                'ProcessedPages': 0,
                'Status': 'PROCESSING'
            }
        )
        print(f"📝 Libro {book_id} registrado en DynamoDB.")

        # 5. Enviamos cada página como un mensaje a SQS
        for idx, page in enumerate(reader.pages):
            page_text = page.extract_text()
            page_number = idx + 1
            
            # Si la página está vacía, evitamos enviarla
            if not page_text.strip():
                print(f"⚠️ Página {page_number} vacía, omitiendo.")
                continue
                
            message_body = {
                "text": page_text,
                "book_id": book_id,
                "page_number": page_number
            }
            
            sqs_client.send_message(
                QueueUrl=SQS_QUEUE_URL,
                MessageBody=json.dumps(message_body)
            )
            
        print(f"✅ Se enviaron las {total_pages} páginas a SQS con éxito.")
        
    except Exception as e:
        print(f"❌ Error en el Splitter: {e}")
        raise e
    finally:
        # Limpieza del archivo temporal para no agotar el almacenamiento de la Lambda
        if os.path.exists(local_pdf_path):
            os.remove(local_pdf_path)
            
    return {
        'statusCode': 200,
        'body': json.dumps('PDF procesado y dividido con éxito')
    }