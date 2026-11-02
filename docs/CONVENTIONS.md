# Template conventions

Every template under `templates/` and `blueprints/` follows these rules.
`scripts/check_library.py` enforces them, and CI fails if one is broken.

## Layout

- `templates/<domain>/<service>-<thing>.yaml`: one deployable building block.
- `blueprints/<name>.yaml`: a complete stack composed from building blocks as nested stacks.
- `legacy/`: the original templates, unsupported and kept for reference.

## Required shape

Each template has:

1. `AWSTemplateFormatVersion: '2010-09-09'` and a `Description`.
2. `Metadata.Library`:
   - `Domain`: must equal the parent directory name.
   - `Summary`: one sentence for the catalog.
   - `Cost`: what bills while the stack sits idle, and what scales with use.
   - `Prerequisites`: a list of what must already exist (`[]` if nothing).
   - Optional exception maps, described below.
3. `Metadata.AWS::CloudFormation::Interface` grouping the parameters.
4. Parameters `ProjectName` and `Environment`, each with a `Description`.
5. At least one `Output`. Every output has a `Description` and an export named
   `!Sub '${AWS::StackName}-<OutputName>'`.

## Rules

| Rule | Requirement |
|---|---|
| Tags | Every taggable resource carries `Project`, `Environment` and `ManagedBy: CloudFormation`. |
| Data protection | Stateful resources set both `DeletionPolicy` and `UpdateReplacePolicy` to `Retain` or `Snapshot`. |
| Physical names | Leave names out so CloudFormation generates them and replacement works. Exceptions go in `PhysicalNames`. |
| Portability | No hardcoded account IDs, regions, Availability Zones or AMI IDs. ARNs use `${AWS::Partition}`; AZs use `!GetAZs`; AMIs use SSM public parameters. |
| Secrets | No password, token or private-key parameters and no `NoEcho`. Use service-managed secrets or take a Secrets Manager ARN. |
| IAM | No `*` or `service:*` actions. `Resource: '*'` is allowed only for actions with no resource-level support, recorded in `WildcardResources`. |
| Network | No `0.0.0.0/0` or `::/0` ingress, and never as a parameter default. Internet-facing resources are recorded in `PublicIngress`. |
| S3 | All four public access block settings on, encryption on. |
| Plain CloudFormation | No transforms, macros or custom resources, so templates deploy with no helper code. |
| Lint | `cfn-lint` reports no errors or warnings. |

## Exception maps

Each is a map of logical ID to the reason, and the checker rejects entries
naming a resource that does not exist:

```yaml
Metadata:
  Library:
    PhysicalNames:
      ExampleRole: GitHub's trust policy needs a predictable role name.
    WildcardResources:
      ExamplePolicy: ecr:GetAuthorizationToken has no resource-level support.
    PublicIngress:
      ExampleSecurityGroup: An internet-facing load balancer must accept public traffic.
```

## Defaults

Choose the safe and cheap option, and let the caller opt in to anything that
costs more. NAT gateways, Multi-AZ and similar paid features are off or minimal
by default unless the resource cannot work without them. Say so in `Cost`.

## Composition

Building blocks take plain values as parameters rather than importing exports,
so they work standalone, with `!ImportValue` in your own templates, or as nested
stacks. Comma-joined outputs such as `PrivateSubnetIds` can be passed directly to
`List<AWS::EC2::Subnet::Id>` parameters.
