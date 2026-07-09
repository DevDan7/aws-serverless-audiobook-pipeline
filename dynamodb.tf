resource "aws_dynamodb_table" "table_SSML" {
  name         = "table-SSML-dev-daniel"
  hash_key     = "BookID" # <-- Cambiado para alinearse con nuestro diseño de negocio
  billing_mode = "PAY_PER_REQUEST"

  attribute {
    name = "BookID" # <-- Debe coincidir exactamente con el hash_key
    type = "S"
  }

  tags = {
    Name        = "table-SSML"
    Environment = "Dev"
  }
}