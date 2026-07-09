# Crear el parámetro cifrado en el Parameter Store de AWS
resource "aws_ssm_parameter" "elevenlabs_key" {
  name        = "/audiobook/dev/elevenlabs_api_key"
  description = "API Key para la integracion con ElevenLabs"
  type        = "SecureString" # <-- "SecureString" cifra el dato usando KMS (Key Management Service) de forma gratuita
  value       = var.elevenlabs_api_key

  tags = {
    Environment = "Dev"
  }
}