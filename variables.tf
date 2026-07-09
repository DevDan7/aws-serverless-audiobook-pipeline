variable "elevenlabs_api_key" {
  type        = string
  description = "API Key secreta para autenticarse en ElevenLabs"
  sensitive   = true # <-- Esto le dice a Terraform que oculte el valor en los logs de la terminal
}