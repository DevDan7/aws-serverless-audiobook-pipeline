# 1. El Rol de Confianza (El que tú escribiste, ¡perfecto!)
resource "aws_iam_role" "lambda_processor_role" {
  name = "audiobook-processor-lambda-role-dev"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

# 2. La Política de Permisos Mínimos
resource "aws_iam_policy" "lambda_processor_policy" {
  name        = "audiobook-processor-lambda-policy-dev"
  description = "Permisos estrictos para la Lambda Procesadora de Audiobooks"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Permiso para CloudWatch (Para poder ver logs/errores en la consola)
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      # Permiso para SQS (Consumir y borrar de la cola principal)
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.audiobook_queue.arn # <-- Vinculado a tu SQS automáticamente
      },
      # Permiso temporal de diagnóstico para Bedrock
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "*" # <-- Comodín temporal para aislar el problema
      },
      # Permiso para Amazon Polly (Sintetizar audio)
      {
        Effect = "Allow"
        Action = [
          "polly:StartSpeechSynthesisTask"
        ]
        Resource = "*" # Polly requiere "*" porque la tarea de síntesis no se limita a un recurso específico
      },
      # Permiso para guardar los audios en S3 (Requerido por Polly)
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.pdf_outputs.arn}/*" # <-- Permiso de escribir dentro de tu bucket de salida
      },
      # Permiso para DynamoDB (Actualizar el contador del libro)
      {
        Effect = "Allow"
        Action = [
          "dynamodb:UpdateItem"
        ]
        Resource = aws_dynamodb_table.table_SSML.arn # <-- Vinculado a tu DynamoDB automáticamente
      },
      # Permiso de Solo Lectura para obtener la API Key de ElevenLabs
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter"
        ]
        Resource = aws_ssm_parameter.elevenlabs_key.arn
      }
    ]
  })
}

# 3. La Unión (Attachment) entre el Rol y la Política
resource "aws_iam_role_policy_attachment" "lambda_processor_attach" {
  role       = aws_iam_role.lambda_processor_role.name
  policy_arn = aws_iam_policy.lambda_processor_policy.arn
}

# Rol para Lambda A
resource "aws_iam_role" "lambda_splitter_role" {
  name = "audiobook-splitter-lambda-role-dev"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

# Política de Permisos para Lambda A
resource "aws_iam_policy" "lambda_splitter_policy" {
  name        = "audiobook-splitter-lambda-policy-dev"
  description = "Permisos para leer S3, escribir en SQS y DynamoDB"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      # Permiso para leer el PDF del bucket de entrada
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.pdf_inputs.arn}/*"
      },
      # Permiso para enviar mensajes a la cola SQS
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.audiobook_queue.arn
      },
      # Permiso para registrar el libro en DynamoDB
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem"]
        Resource = aws_dynamodb_table.table_SSML.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_splitter_attach" {
  role       = aws_iam_role.lambda_splitter_role.name
  policy_arn = aws_iam_policy.lambda_splitter_policy.arn
}