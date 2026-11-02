#!/usr/bin/env bash
# Deploy one template to a sandbox account, show its outputs, then delete the stack.
# Refuses to run unless --account matches the current credentials.
#
#   scripts/smoke_test.sh --account 123456789012 --region us-east-1 \
#     --template templates/integration/sqs-queue.yaml \
#     --params "ProjectName=smoke Environment=dev"
#
# Resources with DeletionPolicy: Retain stay behind after the stack is deleted, and keep billing
# until you remove them by hand. Check each template's Cost note first.
set -euo pipefail

account="" region="" template="" params=""
while [ $# -gt 0 ]; do
  case "$1" in
    --account) account="$2"; shift 2 ;;
    --region) region="$2"; shift 2 ;;
    --template) template="$2"; shift 2 ;;
    --params) params="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 64 ;;
  esac
done
[ -n "$account" ] && [ -n "$region" ] && [ -n "$template" ] || { sed -n 2,10p "$0"; exit 64; }
[ -f "$template" ] || { echo "no such template: $template" >&2; exit 66; }

actual=$(aws sts get-caller-identity --query Account --output text)
if [ "$actual" != "$account" ]; then
  echo "current credentials are for account $actual, not $account; refusing to deploy" >&2
  exit 77
fi

stack="smoke-$(basename "$template" .yaml)-$(date +%s)"
cleanup() {
  echo "Deleting $stack"
  aws cloudformation delete-stack --region "$region" --stack-name "$stack"
  aws cloudformation wait stack-delete-complete --region "$region" --stack-name "$stack"
}
trap cleanup EXIT

# shellcheck disable=SC2086 # params is a space-separated list of Key=Value pairs by design.
aws cloudformation deploy --region "$region" --stack-name "$stack" --template-file "$template" \
  --capabilities CAPABILITY_IAM ${params:+--parameter-overrides $params}
aws cloudformation describe-stacks --region "$region" --stack-name "$stack" \
  --query 'Stacks[0].Outputs' --output table
