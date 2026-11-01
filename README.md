# AWS CloudFormation Template Library

A set of CloudFormation templates for common AWS infrastructure, written to be
deployed as-is or copied into a larger stack.

Every template in this repository passes `cfn-lint` with zero errors, and CI
enforces that on every push (a linter crash fails the build too). Templates are plain CloudFormation with no
transforms, no macros and no external dependencies.

## Quick start

```bash
git clone https://github.com/CoinClubQuincy/AWS-CloudFormation-Infrastructure-Library.git
cd AWS-CloudFormation-Infrastructure-Library

# inspect what a template needs before deploying it
aws cloudformation validate-template --template-body file://S3/Basic-S3-Bucket.yaml

# ENVTag accepts Dev, Prod or Test (case-sensitive); ProjectTag has no default.
aws cloudformation deploy \
  --template-file S3/Basic-S3-Bucket.yaml \
  --stack-name my-bucket \
  --parameter-overrides ENVTag=Dev ProjectTag=demo
```

The bucket is named `<stack-name>-<region>-xxxx-stackbucket`. S3 bucket names
are global across all AWS accounts, so use a lowercase stack name that nobody
else is likely to have used.

Add `--capabilities CAPABILITY_NAMED_IAM` for any template that creates IAM
roles or policies.

## Validating locally

```bash
pip install cfn-lint
cfn-lint VPC/VPC.yaml            # one template
cfn-lint $(find . -name '*.yaml')  # everything
```

## Secrets

The RDS templates (`Database/Basic-RDS.yaml` and
`Database/Basic-RDS-w-Server.yaml`) take no password parameter. They set
`ManageMasterUserPassword: true`, so RDS generates the master password, stores
it in AWS Secrets Manager and, by default, rotates it every seven days. The
password never passes through the stack parameters. The `DBSecretArn` stack
output is the ARN of that secret:

```bash
aws secretsmanager get-secret-value --secret-id <DBSecretArn>
```

The identity that deploys the stack needs `secretsmanager:CreateSecret`,
`secretsmanager:TagResource` and `kms:DescribeKey`. RDS deletes the secret
when it deletes the DB instance.

## Templates


### API

| Template | Creates | Required parameters |
|---|---|---|
| [`API/API-Gateway.yaml`](API/API-Gateway.yaml) | API Gateway REST API with no resources, methods, deployment or stage. Add those before it can serve requests. | `ProjectTag` |

### Billing

| Template | Creates | Required parameters |
|---|---|---|
| [`Billing/default_price_alarms.yaml`](Billing/default_price_alarms.yaml) | 'CloudFormation template to create AWS Billing Alarms from $50 to $700 in $50 intervals' | `NotificationEmail` |

### CI/CD

| Template | Creates | Required parameters |
|---|---|---|
| [`CodePipelines/Repos/CodeCommit.yaml`](CodePipelines/Repos/CodeCommit.yaml) | CodeCommit repository. | `ProjectTag`, `Description` |
| [`CodePipelines/Repos/ECR.yaml`](CodePipelines/Repos/ECR.yaml) | ECR repository named after the stack, so the stack name must be lowercase. No lifecycle policy. | `ProjectTag` |
| [`CodePipelines/codepipeline-CF.yaml`](CodePipelines/codepipeline-CF.yaml) | CodePipeline that deploys a CloudFormation stack through a change set, with a manual approval gate between test and production. | `PipelineName`, `S3Bucket`, `Email` |
| [`CodePipelines/codepipeline-codecommit.yaml`](CodePipelines/codepipeline-codecommit.yaml) | CodePipeline sourced from CodeCommit, with its own CodeBuild project and scoped service roles. The repository needs a `buildspec.yml` at its root. | `AppName`, `BranchName`, `BuildImage` |
| [`CodePipelines/codepipeline-docker-build-lambda.yaml`](CodePipelines/codepipeline-docker-build-lambda.yaml) | CodeCommit and ECR repositories, a privileged CodeBuild project, and a CodePipeline that runs CodeCommit, then CodeBuild, then CodeDeploy. The CodeDeploy deployment group is an EC2/on-premises one with no targets. No Lambda function is created. | `ResourceName` |
| [`CodePipelines/codepipeline-github.yaml`](CodePipelines/codepipeline-github.yaml) | CodePipeline sourced from GitHub. | `GitHubOwner`, `GitHubSecret`, `GitHubOAuthToken`, `VersionTag`, `ProjectTag` |

### Databases and queries

| Template | Creates | Required parameters |
|---|---|---|
| [`Database/Basic-DynamoDB.yaml`](Database/Basic-DynamoDB.yaml) | DynamoDB table with a configurable partition and sort key. | `PrimaryKey`, `SortKey`, `ProjectTag`, `DyanmoMap` |
| [`Database/Basic-RDS-w-Server.yaml`](Database/Basic-RDS-w-Server.yaml) | RDS instance plus an EC2 application server in the same VPC. | `PrivateIP`, `VPC`, `Subnet1`, `Subnet2`, `DBUsername`, `ProjectTag`, `KeyName` |
| [`Database/Basic-RDS.yaml`](Database/Basic-RDS.yaml) | RDS instance inside a VPC with a parameterised engine and size. | `PrivateIP`, `VPC`, `Subnet1`, `Subnet2`, `DBUsername`, `ProjectTag` |
| [`Database/Querys/AthenaLong.yaml`](Database/Querys/AthenaLong.yaml) | Athena named query, long form. | `Database`, `Description`, `Query`, `Query2`, `Query3`, `Query4` (+16) |
| [`Database/Querys/AthenaShort.yaml`](Database/Querys/AthenaShort.yaml) | Athena named query, short form. | `Database`, `Description`, `Query`, `Query2`, `Query3`, `Query4` (+6) |
| [`Database/Querys/OpenSearch.yaml`](Database/Querys/OpenSearch.yaml) | Amazon OpenSearch Service domain. Replaces the former Elasticsearch template: the service was renamed to OpenSearch Service and AWS::Elasticsearch::Domain is superseded by AWS::OpenSearchService::Domain. Encrypted at rest and in transit, never open to the public internet. | `DomainName`, `SubnetIds`, `SecurityGroupIds` |

### IAM

| Template | Creates | Required parameters |
|---|---|---|
| [`IAM/IAM.yaml`](IAM/IAM.yaml) | Reusable IAM building blocks: a service role assumable by a chosen AWS service, an optional EC2 instance profile, and a customer-managed policy scoped to one S3 prefix. Written least-privilege by default rather than with wildcard actions. | `RoleName`, `ScopedBucketName` |

### S3

| Template | Creates | Required parameters |
|---|---|---|
| [`S3/Basic-S3-Bucket.yaml`](S3/Basic-S3-Bucket.yaml) | S3 bucket with tagging. | `ProjectTag` |
| [`S3/S3-Website.yaml`](S3/S3-Website.yaml) | S3 bucket configured for static website hosting. | `ProjectTag` |

### Compute

| Template | Creates | Required parameters |
|---|---|---|
| [`Servers/Basic-Server-Https.yaml`](Servers/Basic-Server-Https.yaml) | EC2 instance in an HTTPS target group, plus an internet-facing Application Load Balancer with no listener or certificate. Add an HTTPS listener before it forwards traffic. | `ProjectTag`, `VPC`, `Subnet1`, `Subnet2`, `KeyName` |

### Messaging and streaming

| Template | Creates | Required parameters |
|---|---|---|
| [`Transit-Notify/Kinesis.yaml`](Transit-Notify/Kinesis.yaml) | Kinesis data stream. | `ProjectTag` |
| [`Transit-Notify/SNS-Sub.yaml`](Transit-Notify/SNS-Sub.yaml) | SNS topic subscriptions. Creates an email or HTTPS subscription against an existing topic, plus an optional SQS subscription complete with the queue policy SNS needs in order to deliver. Encrypted queue by default. | `TopicArn`, `Endpoint` (unless `Protocol` is `sqs`) |
| [`Transit-Notify/SNS-Topics.yaml`](Transit-Notify/SNS-Topics.yaml) | SNS topic. | `ProjectTag` |
| [`Transit-Notify/SQS.yaml`](Transit-Notify/SQS.yaml) | SQS queue. | `ProjectTag` |

### Networking

| Template | Creates | Required parameters |
|---|---|---|
| [`VPC/SG.yaml`](VPC/SG.yaml) | Security group with parameterised ingress rules. | `ProjectTag` |
| [`VPC/VPC.yaml`](VPC/VPC.yaml) | Multi-AZ VPC with public and private subnets, route tables, NAT and an internet gateway. | `ProjectTag` |

## Contributing

Templates must pass `cfn-lint` with zero errors before merge. Warnings are
reported by CI but do not block.

## License

Apache License 2.0. See [LICENSE](LICENSE).
