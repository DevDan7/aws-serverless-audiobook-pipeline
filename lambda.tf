# Este bloque toma tu archivo Python y crea un .zip temporal en tu computadora
data "archive_file" "lambda_processor_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda_processor.py"  # Tu archivo de código
  output_path = "${path.module}/lambda_processor.zip" # Dónde se guardará el zip temporal
}

resource "aws_lambda_function" "audiobook_processor" {
  filename      = data.archive_file.lambda_processor_zip.output_path
  function_name = "audiobook-processor-dev-daniel"
  role          = aws_iam_role.lambda_processor_role.arn
  handler       = "lambda_processor.lambda_handler" # Busca el archivo lambda_processor.py y la función lambda_handler
  runtime       = "python3.12"
  timeout       = 60  # Le damos 1 minuto para que Bedrock y Polly tengan tiempo de responder
  memory_size   = 128 # Suficiente para procesamiento de texto

  # Esta línea es magia pura: le dice a Terraform que si tu código de Python cambia, 
  # vuelva a empaquetar y actualizar la Lambda automáticamente.
  source_code_hash = data.archive_file.lambda_processor_zip.output_base64sha256

  # Inyección de variables de entorno
  environment {
    variables = {
      DYNAMODB_TABLE      = aws_dynamodb_table.table_SSML.name
      OUTPUT_BUCKET_NAME  = aws_s3_bucket.pdf_outputs.id                          # <-- ¡Esta es la línea clave que agregamos!
      ELEVENLABS_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb" # <-- Agrega esta línea con tu ID
    }
  }

  tags = {
    Name        = "audiobook-processor"
    Environment = "Dev"
  }
}

# El Puente: Conecta SQS como disparador (Trigger) de la Lambda
resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.audiobook_queue.arn
  function_name    = aws_lambda_function.audiobook_processor.arn
  batch_size       = 1 # Procesa 1 mensaje a la vez para no sobrecargar
  enabled          = true
}

# 1. Empaquetar el código de la Lambda A
data "archive_file" "lambda_splitter_zip" {
  type        = "zip"
  source_dir  = "${path.module}/src/lambda_splitter" # Guardaremos el código en esta subcarpeta
  output_path = "${path.module}/lambda_splitter.zip"
}

# 2. La Función Lambda A
resource "aws_lambda_function" "audiobook_splitter" {
  filename      = data.archive_file.lambda_splitter_zip.output_path
  function_name = "audiobook-splitter-dev-daniel"
  role          = aws_iam_role.lambda_splitter_role.arn
  handler       = "lambda_splitter.lambda_handler"
  runtime       = "python3.12"
  timeout       = 120 # 2 minutos (suficiente para PDFs grandes)
  memory_size   = 256 # Le damos un poco más de RAM para procesar el PDF en memoria

  source_code_hash = data.archive_file.lambda_splitter_zip.output_base64sha256

  environment {
    variables = {
      SQS_QUEUE_URL  = aws_sqs_queue.audiobook_queue.id
      DYNAMODB_TABLE = aws_dynamodb_table.table_SSML.name
    }
  }
}

# 3. Permiso para que S3 invoque a la Lambda
resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.audiobook_splitter.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.pdf_inputs.arn
}

# 4. El Trigger de S3 (Gatillo)
resource "aws_s3_bucket_notification" "s3_trigger" {
  bucket = aws_s3_bucket.pdf_inputs.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.audiobook_splitter.arn
    events              = ["s3:ObjectCreated:*"]
    filter_suffix       = ".pdf" # Solo dispara con archivos PDF
  }

  depends_on = [aws_lambda_permission.allow_s3] # Garantiza que el permiso exista antes de crear el trigger
}
