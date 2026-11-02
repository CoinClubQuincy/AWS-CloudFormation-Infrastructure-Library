# Security scan decisions

CI runs [Checkov](https://github.com/bridgecrewio/checkov) over `templates/` and fails on any
finding not listed here. These checks are skipped because the library makes the choice a
parameter, because the check cannot read a conditional, or because the default trades a small
risk for a real recurring cost. Review them against your own requirements.

## The check cannot read the template's condition

| Check | Template | Why it is a false finding |
|---|---|---|
| `CKV_AWS_19` | `storage/s3-bucket` | Encryption is always on. The algorithm is chosen by `!If` on `KmsKeyArn`. |
| `CKV_AWS_27` | `integration/sqs-queue` | Encryption is always on: SSE-SQS by default, KMS when `KmsKeyArn` is set. |
| `CKV_AWS_174` | `edge/cloudfront-s3-site` | `TLSv1.2_2021` is set when a custom certificate is used. The default CloudFront certificate has no such setting. |

## Available as a parameter, off by default for cost

| Check | Template | Parameter |
|---|---|---|
| `CKV_AWS_65` | `containers/ecs-cluster` | `ContainerInsights` |
| `CKV_AWS_76` | `integration/api-gateway-rest-lambda` | `EnableAccessLogs` |
| `CKV_AWS_91` | `networking/load-balancer-{alb,nlb}` | `AccessLogBucketName` |
| `CKV_AWS_116` | `compute/lambda-function` | `DeadLetterQueueArn` |
| `CKV_AWS_119` | `database/dynamodb-table` | `KmsKeyArn` |
| `CKV_AWS_157` | `database/rds-instance` | `MultiAz` |

## Accepted defaults

| Check | Applies to | Reason |
|---|---|---|
| `CKV_AWS_18`, `CKV_AWS_21` | Log, trail, Config and artifact buckets; `CKV_AWS_18` also on site buckets | These hold logs or short-lived objects with lifecycle expiry. Access-logging a log bucket recurses. CloudTrail integrity comes from log file validation. |
| `CKV_AWS_35` | `security/cloudtrail` | Uses SSE-S3. A customer-managed key adds a monthly charge and key policy upkeep. |
| `CKV_AWS_58` | `containers/eks-cluster` | EKS applies default envelope encryption to Kubernetes API data on supported versions. Check this for your version if you need your own key. |
| `CKV_AWS_73`, `CKV_AWS_120` | `integration/api-gateway-rest-lambda` | X-Ray and stage caching bill by use, and caching can serve stale or private data if set carelessly. |
| `CKV_AWS_84`, `CKV_AWS_317`, `CKV_AWS_85` | OpenSearch, DocumentDB | Log exports bill for ingestion, and OpenSearch audit logs need fine-grained access control first. |
| `CKV_AWS_86` | `edge/cloudfront-s3-site` | Standard logs need a bucket with ACLs enabled, which the library's log bucket deliberately disables. |
| `CKV_AWS_118` | RDS, Aurora | Enhanced monitoring needs an extra role and bills through CloudWatch Logs. |
| `CKV_AWS_136` | `containers/ecr-repository` | Uses AES-256. KMS adds per-request charges. |
| `CKV_AWS_158` | Log groups | Log data is encrypted by CloudWatch Logs by default. `observability/log-group` takes `KmsKeyArn` when you need your own key. |
| `CKV_AWS_161`, `CKV_AWS_162` | RDS, Aurora | Credentials are generated and stored in Secrets Manager. IAM database authentication is not supported on every engine version. |
| `CKV_AWS_173` | `compute/lambda-function` | Environment variables hold non-secret configuration. Secrets belong in Secrets Manager. |
| `CKV_AWS_195` | `analytics/glue-crawler` | A security configuration must be created per account and is only useful with a customer-managed key. |
