terraform {
  required_version = ">= 1.11.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

variable "github_repository" {
  description = "Exact GitHub OWNER/REPO for the designated environment."
  type        = string
}

variable "github_environment" {
  type    = string
  default = "cloud-plan"
}

variable "github_oidc_provider_arn" {
  description = "Existing account OIDC provider for token.actions.githubusercontent.com."
  type        = string
}

variable "plan_policy_arn" {
  description = "Existing scoped cloud read and Terraform state locking policy."
  type        = string
}

data "aws_iam_policy_document" "github" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.github_oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:environment:${var.github_environment}"]
    }
  }
}

resource "aws_iam_role" "github" {
  name                 = "vllm-ops-github-plan"
  assume_role_policy   = data.aws_iam_policy_document.github.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "github" {
  role       = aws_iam_role.github.name
  policy_arn = var.plan_policy_arn
}

output "role_arn" {
  value = aws_iam_role.github.arn
}
