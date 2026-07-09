resource "aws_s3_bucket" "pdf_inputs" {
  bucket = "pdf-inputs-audiobooks-dev-daniel"

  tags = {
    Name        = "pdf-inputs"
    Environment = "Dev"
  }
}

resource "aws_s3_bucket" "pdf_outputs" {
  bucket = "pdf-outputs-audiobooks-dev-daniel"

  tags = {
    Name        = "pdf-outputs"
    Environment = "Dev"
  }
}