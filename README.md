# Components

Shared components mono-repo for Porth (Login & Multi-tenancy) and Twr (Ops Agent).

## Pipeline Test

`GET /health` — health check Lambda behind API Gateway, deployed via GitHub Actions + AWS OIDC.

## Setup

Add the `AWS_ROLE_ARN` secret to the repo (the IAM role ARN your GitHub OIDC provider assumes).

## Deployed Resources

- **Lambda:** `porth-health-check` (Python 3.13)
- **API Gateway:** HTTP API with `/health` route
- **Region:** eu-west-2
