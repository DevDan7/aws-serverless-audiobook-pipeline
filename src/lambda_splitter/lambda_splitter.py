import os
import json
import boto3
import urllib.parse
from io import BytesIO
from pypdf import PdfReader
from concurrent.futures import ThreadPoolExecutor

# Inicializar clientes de AWS
s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')
db_client = boto3.resource('dynamodb')
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1') # Cambia la región si es necesario

# Variables de entorno
QUEUE_URL = os.environ['SQS_QUEUE_URL']
TABLE_NAME = os.environ['DYNAMODB_TABLE']
table = db_client.Table(TABLE_NAME)

def evaluate_page_with_bedrock(page_num, text):
    """
    Usa Amazon Bedrock (Nova Micro) para determinar si la página contiene
    contenido principal narrable (KEEP) o si es basura estructural (DISCARD).
    """
    if not text.strip():
        return page_num, "DISCARD", "Página vacía"

    # Limitamos el texto enviado para no consumir tokens innecesarios (primeros 1500 caracteres)
    sample_text = text[:1500]

    # Prompt ultra-optimizado para respuesta determinista
    prompt = f"""Analiza el siguiente texto de la página de un libro. 
Determina si contiene contenido principal para ser narrado en un audiolibro (capítulos, historias, explicaciones, conceptos) o si es contenido estructural/basura que debe ser ignorado (índices, tablas de contenido, páginas de derechos de autor, bibliografía, dedicatorias breves, páginas de tareas con líneas vacías, glosarios).

Responde ESTRICTAMENTE con un objeto JSON que tenga la clave "decision" con valor "KEEP" o "DISCARD". No agregues explicaciones, no saludes, no uses Markdown.

Texto:
\"\"\"{sample_text}\"\"\"

JSON:"""

    # Removido 'maxNewTokens' para evitar el conflicto con el validador de Bedrock.
    # Mantenemos 'temperature': 0.0 para asegurar respuestas deterministas.
    body = json.dumps({
        "inferenceConfig": {
            "temperature": 0.0
        },
        "messages": [
            {
                "role": "user",
                "content": [{"text": prompt}]
            }
        ]
    })

    try:
        response = bedrock_client.invoke_model(
            modelId="amazon.nova-micro-v1:0",
            contentType="application/json",
            accept="application/json",
            body=body
        )
        response_body = json.loads(response.get('body').read())
        output_text = response_body['output']['message']['content'][0]['text'].strip()
        
        # Limpieza básica por si el modelo devuelve markdown
        if "```json" in output_text:
            output_text = output_text.split("```json")[1].split("```")[0].strip()
        elif "```" in output_text:
            output_text = output_text.split("```")[1].split("```")[0].strip()

        result = json.loads(output_text)
        decision = result.get("decision", "KEEP")
        return page_num, decision, text

    except Exception as e:
        print(f"Error procesando página {page_num} con Bedrock: {str(e)}")
        # En caso de error, por seguridad conservamos la página para no perder contenido
        return page_num, "KEEP", text

def lambda_handler(event, context):
    # Obtener información del archivo S3
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    book_id = os.path.splitext(os.path.basename(key))[0]

    print(f"Iniciando procesamiento del libro: {book_id} desde {bucket}/{key}")

    # Descargar PDF desde S3
    response = s3_client.get_object(Bucket=bucket, Key=key)
    pdf_file = BytesIO(response['Body'].read())
    
    reader = PdfReader(pdf_file)
    total_pages = len(reader.pages)
    
    print(f"Total de páginas detectadas: {total_pages}")

    # Preparar las páginas para procesamiento concurrente
    pages_to_process = []
    for idx, page in enumerate(reader.pages):
        pages_to_process.append((idx + 1, page.extract_text()))

    evaluated_pages = []
    
    # Procesamiento concurrente de páginas con Bedrock usando un pool de 10 hilos
    print("Iniciando clasificación con Amazon Bedrock...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(evaluate_page_with_bedrock, num, txt) for num, txt in pages_to_process]
        for future in futures:
            evaluated_pages.append(future.result())

    # Filtrar solo las páginas clasificadas como KEEP
    valid_pages = [p for p in evaluated_pages if p[1] == "KEEP"]
    final_page_count = len(valid_pages)
    
    print(f"Curación completada. Páginas originales: {total_pages} -> Páginas válidas a procesar: {final_page_count}")

    if final_page_count == 0:
        print("No se encontraron páginas válidas para procesar.")
        return {"statusCode": 200, "body": "No valid pages to process."}

    # Registrar el libro en DynamoDB con el total de páginas REALES filtradas
    table.put_item(
        Item={
            'BookID': book_id,
            'TotalPages': final_page_count,
            'ProcessedPages': 0,
            'Status': 'PROCESSING'
        }
    )

    # Enviar las páginas válidas a SQS con su índice secuencial correcto
    for sequential_idx, (orig_num, _, text) in enumerate(valid_pages, start=1):
        message_body = {
            "BookID": book_id,
            "PageNum": sequential_idx,          # Nuevo índice secuencial para la unión final
            "OriginalPageNum": orig_num,         # Guardamos el original para trazabilidad
            "TotalPages": final_page_count,
            "Text": text
        }
        
        sqs_client.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(message_body)
        )

    print(f"Se han enviado {final_page_count} mensajes a SQS para el libro {book_id}")
    return {
        "statusCode": 200,
        "body": json.dumps(f"Procesado exitosamente. {final_page_count} de {total_pages} páginas enviadas a síntesis.")
    }