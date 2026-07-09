import boto3
from botocore.exceptions import ClientError

def generar_ssml(texto_crudo):
    # 1. Inicializamos el cliente de Bedrock Runtime
    # Usamos us-east-1 (N. Virginia) porque Nova Pro suele estar disponible ahí
    try:
        client = boto3.client('bedrock-runtime', region_name='us-east-1')
    except Exception as e:
        print(f"Error al inicializar Boto3. ¿Ejecutaste aws configure?: {e}")
        return None

    # 2. El System Prompt estricto (El "cerebro" del estilo)
    system_prompt = [{
        "text": """Eres un procesador de texto automatizado experto en SSML.
Tu objetivo es simular el estilo de oratoria de un motivador de alto impacto: 
alta energía, pausas dramáticas y énfasis en el mindset.

REGLAS ESTRICTAS:
1. NO saludes, NO des explicaciones, NO digas 'Aquí tienes el texto'.
2. Devuelve ÚNICAMENTE código válido envuelto en la etiqueta <speak>.
3. Usa <break time="800ms"/> para pausas de impacto.
4. Usa <emphasis level="strong"> para palabras clave sobre éxito o acción.
5. Usa <prosody rate="fast" volume="loud"> para llamados a la acción.
"""
    }]

    # 3. Formateamos el mensaje del usuario según la API Converse de Bedrock
    messages = [{
        "role": "user",
        "content": [{"text": texto_crudo}]
    }]

    print("Enviando texto a Amazon Bedrock (Nova Pro)... ⏳\n")

    try:
        # 4. Invocamos al modelo
        # OJO: 'us.amazon.nova-pro-v1:0' es el ID de Nova Pro. 
        response = client.converse(
            modelId='us.amazon.nova-pro-v1:0',
            messages=messages,
            system=system_prompt
        )
        
        # 5. Extraemos el texto de la respuesta JSON
        ssml_generado = response['output']['message']['content'][0]['text']
        return ssml_generado

    except ClientError as err:
        error_code = err.response['Error']['Code']
        error_msg = err.response['Error']['Message']
        print(f"❌ Error de AWS: {error_code} - {error_msg}")
        return None
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return None

# --- BLOQUE DE EJECUCIÓN (Solo corre si ejecutas este archivo directamente) ---
if __name__ == "__main__":
    texto_prueba = "O código foi destravado. Você precisa agir agora. Chega de desculpas e comece a construir seu futuro."
    
    resultado = generar_ssml(texto_prueba)
    
    if resultado:
        print("✅ --- RESULTADO SSML GENERADO --- ✅")
        print(resultado)