# 1. Crear el canal SNS
resource "aws_sns_topic" "audiobook_notifications" {
  name = "audiobook-notifications-dev-daniel"
}

# 2. Suscribir tu correo electrónico real al canal
resource "aws_sns_topic_subscription" "email_sub" {
  topic_arn = aws_sns_topic.audiobook_notifications.arn
  protocol  = "email"
  endpoint  = "danielsvillegas17@gmail.com"
}