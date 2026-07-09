# 1. Fila Principal de Procesamiento
resource "aws_sqs_queue" "audiobook_queue" {
  name                       = "audiobook-processing-queue-dev-daniel"
  delay_seconds              = 0     # <-- Cambiado a 0 para que sea instantáneo
  message_retention_seconds  = 86400 # 1 día de retención
  receive_wait_time_seconds  = 10    # Long Polling (ahorra dinero en Lambdas)
  visibility_timeout_seconds = 360

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.audiobook_dlq.arn
    maxReceiveCount     = 4 # Si falla 4 veces, va a la DLQ
  })

  tags = {
    Name        = "audiobook-processing-queue"
    Environment = "Dev"
  }
}

# 2. Fila Muerta (DLQ - Dead Letter Queue)
resource "aws_sqs_queue" "audiobook_dlq" {
  name = "audiobook-processing-dlq-dev-daniel"

  tags = {
    Name        = "audiobook-processing-dlq"
    Environment = "Dev"
  }
}

# 3. Política de Permiso para la Fila Muerta
resource "aws_sqs_queue_redrive_allow_policy" "audiobook_dlq_redrive_policy" {
  queue_url = aws_sqs_queue.audiobook_dlq.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue",
    sourceQueueArns   = [aws_sqs_queue.audiobook_queue.arn]
  })
}