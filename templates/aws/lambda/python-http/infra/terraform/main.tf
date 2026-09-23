terraform {
  required_version = "= 1.14.9"
  required_providers {
    aws     = { source = "hashicorp/aws", version = "= 6.0.0" }
    archive = { source = "hashicorp/archive", version = "= 2.7.1" }
  }
  backend "s3" {}
}
provider "aws" {
  region              = var.region
  allowed_account_ids = [var.account_id]
  default_tags { tags = { managed_by = "ea-nextgen-template", instance = var.instance, owner_id = var.owner_id, purpose = var.purpose } }
}
locals {
  name = "ea-${var.instance}-${substr(sha256(var.owner_id), 0, 8)}"
}
data "archive_file" "app" {
  type        = "zip"
  source_file = "${path.module}/../../app/handler.py"
  output_path = "${path.module}/application.zip"
}
resource "aws_cloudwatch_log_group" "app" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = var.retention_days
  skip_destroy      = var.purpose == "production"
}
resource "aws_iam_role" "app" {
  name               = local.name
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy" "logs" {
  role   = aws_iam_role.app.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.app.arn}:*" }] })
}
resource "aws_lambda_function" "app" {
  function_name    = local.name
  role             = aws_iam_role.app.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.app.output_path
  source_code_hash = data.archive_file.app.output_base64sha256
  memory_size      = var.purpose == "production" ? 512 : 256
  timeout          = 10
  publish          = true
  environment { variables = { SOURCE_REVISION = var.revision } }
  depends_on = [aws_iam_role_policy.logs]
}
output "function_name" { value = aws_lambda_function.app.function_name }
output "resource_ids" { value = [aws_lambda_function.app.arn, aws_cloudwatch_log_group.app.arn, aws_iam_role.app.arn] }
