#!/usr/bin/env python3
"""Enforce docs/CONVENTIONS.md and generate docs/CATALOG.md.

Usage:
  check_library.py                 check every template and that the catalog is current
  check_library.py --write-catalog check, then regenerate docs/CATALOG.md
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from cfnlint.decode import cfn_yaml
from cfnlint.schema.manager import PROVIDER_SCHEMA_MANAGER

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "docs" / "CATALOG.md"
REQUIRED_TAGS = {"Project", "Environment", "ManagedBy"}
REGION = "us-east-1"

STATEFUL = {
    "AWS::S3::Bucket", "AWS::DynamoDB::Table", "AWS::DynamoDB::GlobalTable",
    "AWS::RDS::DBInstance", "AWS::RDS::DBCluster", "AWS::EFS::FileSystem",
    "AWS::KMS::Key", "AWS::OpenSearchService::Domain",
    "AWS::ElastiCache::ReplicationGroup", "AWS::ElastiCache::ServerlessCache",
    "AWS::Cognito::UserPool", "AWS::Backup::BackupVault", "AWS::ECR::Repository",
    "AWS::RedshiftServerless::Namespace", "AWS::DocDB::DBCluster",
    "AWS::Neptune::DBCluster", "AWS::SecretsManager::Secret",
}
PHYSICAL_NAME_PROPS = {
    "AWS::S3::Bucket": "BucketName",
    "AWS::DynamoDB::Table": "TableName",
    "AWS::IAM::Role": "RoleName",
    "AWS::IAM::ManagedPolicy": "ManagedPolicyName",
    "AWS::SQS::Queue": "QueueName",
    "AWS::SNS::Topic": "TopicName",
    "AWS::Lambda::Function": "FunctionName",
    "AWS::ECS::Cluster": "ClusterName",
    "AWS::ECS::Service": "ServiceName",
    "AWS::EKS::Cluster": "Name",
    "AWS::ECR::Repository": "RepositoryName",
    "AWS::Logs::LogGroup": "LogGroupName",
    "AWS::RDS::DBInstance": "DBInstanceIdentifier",
    "AWS::RDS::DBCluster": "DBClusterIdentifier",
    "AWS::EC2::SecurityGroup": "GroupName",
    "AWS::Cognito::UserPool": "UserPoolName",
    "AWS::StepFunctions::StateMachine": "StateMachineName",
    "AWS::ElasticLoadBalancingV2::LoadBalancer": "Name",
}
SECRET_PARAM = re.compile(r"password|passwd|secret|token|privatekey|apikey", re.I)
SECRET_PARAM_OK = re.compile(r"^Enable|(Arn|Name|Ttl|Validity|Rotation\w*|Days|Length)$")
HARDCODED = [
    (re.compile(r"arn:aws(-[a-z-]+)?:"), "hardcoded partition; use arn:${AWS::Partition}:"),
    (re.compile(r"(?<![0-9.])[0-9]{12}(?![0-9])"), "looks like a hardcoded account ID"),
    (re.compile(r"\b(us|eu|ap|sa|ca|me|af)-[a-z]+-[0-9][a-z]\b"), "hardcoded Availability Zone"),
    (re.compile(r"\bami-[0-9a-f]{8,}\b"), "hardcoded AMI ID"),
]
OPEN_CIDRS = {"0.0.0.0/0", "::/0"}
INGRESS_TYPES = {"AWS::EC2::SecurityGroup", "AWS::EC2::SecurityGroupIngress"}


def load(path: Path) -> dict:
    return cfn_yaml.load(str(path))


def plain(node):
    """Strip cfn-lint's node wrappers into ordinary Python values."""
    if isinstance(node, dict):
        return {str(k): plain(v) for k, v in node.items()}
    if isinstance(node, list):
        return [plain(v) for v in node]
    if isinstance(node, str):
        return str(node)
    return node


def walk(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)
    else:
        yield node


def iam_statements(node):
    if isinstance(node, dict):
        statement = node.get("Statement")
        if statement is not None:
            yield from statement if isinstance(statement, list) else [statement]
        for value in node.values():
            yield from iam_statements(value)
    elif isinstance(node, list):
        for value in node:
            yield from iam_statements(value)


def tag_property(resource_type: str) -> str | None:
    try:
        schema = PROVIDER_SCHEMA_MANAGER.get_resource_schema(REGION, resource_type).schema
    except Exception:
        return None
    tagging = schema.get("tagging") or {}
    if tagging.get("taggable") is False:
        return None
    configured = tagging.get("tagProperty")
    if configured:
        name = configured.rsplit("/", 1)[-1]
        if name in schema.get("properties", {}):
            return name
    return "Tags" if "Tags" in schema.get("properties", {}) else None


def tag_keys(tags) -> set[str]:
    if isinstance(tags, dict):
        if len(tags) == 1 and next(iter(tags)).startswith("Fn::"):
            return set()
        return set(tags)
    if isinstance(tags, list):
        return {t["Key"] for t in tags if isinstance(t, dict) and isinstance(t.get("Key"), str)}
    return set()


def check_template(path: Path) -> list[str]:
    rel = path.relative_to(ROOT)
    errors: list[str] = []
    err = errors.append
    try:
        doc = plain(load(path))
    except Exception as exc:  # a template that cannot parse fails the check
        return [f"{rel}: cannot parse: {exc}"]

    params = doc.get("Parameters", {})
    resources = doc.get("Resources", {})
    outputs = doc.get("Outputs", {})
    meta = doc.get("Metadata", {})
    lib = meta.get("Library", {})
    is_blueprint = rel.parts[0] == "blueprints"

    if not doc.get("Description"):
        err(f"{rel}: missing Description")
    if doc.get("AWSTemplateFormatVersion") != "2010-09-09":
        err(f"{rel}: AWSTemplateFormatVersion must be 2010-09-09")
    if "Transform" in doc:
        err(f"{rel}: transforms are not allowed")

    expected_domain = "blueprints" if is_blueprint else rel.parts[1]
    if lib.get("Domain") != expected_domain:
        err(f"{rel}: Metadata.Library.Domain must be '{expected_domain}'")
    for key in ("Summary", "Cost"):
        if not lib.get(key):
            err(f"{rel}: Metadata.Library.{key} is required")
    if not isinstance(lib.get("Prerequisites"), list):
        err(f"{rel}: Metadata.Library.Prerequisites must be a list")
    if "AWS::CloudFormation::Interface" not in meta:
        err(f"{rel}: Metadata must include AWS::CloudFormation::Interface")

    for name in ("ProjectName", "Environment"):
        if name not in params:
            err(f"{rel}: missing required parameter {name}")
    for name, param in params.items():
        if not param.get("Description"):
            err(f"{rel}: parameter {name} has no Description")
        if param.get("NoEcho"):
            err(f"{rel}: parameter {name} uses NoEcho; secrets must not be parameters")
        if SECRET_PARAM.search(name) and not SECRET_PARAM_OK.search(name):
            err(f"{rel}: parameter {name} looks like a secret; take a Secrets Manager ARN instead")
        if str(param.get("Default")) in OPEN_CIDRS:
            err(f"{rel}: parameter {name} defaults to an open CIDR")

    if not outputs:
        err(f"{rel}: must define at least one output")
    for name, output in outputs.items():
        if not output.get("Description"):
            err(f"{rel}: output {name} has no Description")
        export = (output.get("Export") or {}).get("Name")
        wanted = {"Fn::Sub": "${AWS::StackName}-" + name}
        if export != wanted:
            err(f"{rel}: output {name} must export !Sub '${{AWS::StackName}}-{name}'")

    exceptions = {}
    for key in ("PhysicalNames", "WildcardResources", "PublicIngress"):
        exceptions[key] = lib.get(key) or {}
        for logical_id, reason in exceptions[key].items():
            if logical_id not in resources:
                err(f"{rel}: {key} names unknown resource {logical_id}")
            if not reason:
                err(f"{rel}: {key}.{logical_id} needs a reason")

    if not resources:
        err(f"{rel}: no resources")
    for logical_id, resource in resources.items():
        rtype = resource.get("Type", "")
        props = resource.get("Properties") or {}
        where = f"{rel}: {logical_id} ({rtype})"

        if rtype.startswith("Custom::") or rtype == "AWS::CloudFormation::CustomResource":
            err(f"{where}: custom resources are not allowed")

        tag_prop = tag_property(rtype)
        if tag_prop:
            missing = REQUIRED_TAGS - tag_keys(props.get(tag_prop))
            if missing:
                err(f"{where}: missing tags {sorted(missing)} on {tag_prop}")

        # An instance inside a cluster holds no data of its own; the cluster carries the policy.
        in_cluster = rtype == "AWS::RDS::DBInstance" and "DBClusterIdentifier" in props
        if rtype in STATEFUL and not in_cluster:
            for policy in ("DeletionPolicy", "UpdateReplacePolicy"):
                if resource.get(policy) not in ("Retain", "Snapshot", "RetainExceptOnCreate"):
                    err(f"{where}: {policy} must be Retain or Snapshot")

        name_prop = PHYSICAL_NAME_PROPS.get(rtype)
        if name_prop in props and logical_id not in exceptions["PhysicalNames"]:
            err(f"{where}: sets {name_prop}; let CloudFormation name it or record it in PhysicalNames")

        if rtype == "AWS::S3::Bucket":
            block = props.get("PublicAccessBlockConfiguration") or {}
            for setting in ("BlockPublicAcls", "BlockPublicPolicy", "IgnorePublicAcls", "RestrictPublicBuckets"):
                if block.get(setting) is not True:
                    err(f"{where}: PublicAccessBlockConfiguration.{setting} must be true")
            if "BucketEncryption" not in props:
                err(f"{where}: BucketEncryption is required")

        if rtype in INGRESS_TYPES and logical_id not in exceptions["PublicIngress"]:
            rules = props.get("SecurityGroupIngress", []) if rtype.endswith("SecurityGroup") else [props]
            for rule in rules if isinstance(rules, list) else []:
                if isinstance(rule, dict) and any(isinstance(rule.get(k), str) and rule[k] in OPEN_CIDRS for k in ("CidrIp", "CidrIpv6")):
                    err(f"{where}: open ingress must be recorded in PublicIngress")

        for statement in iam_statements(props):
            if not isinstance(statement, dict) or statement.get("Effect") != "Allow":
                continue
            actions = statement.get("Action", [])
            for action in actions if isinstance(actions, list) else [actions]:
                # A KMS key policy must grant the account kms:* or the key becomes unmanageable.
                if rtype != "AWS::KMS::Key" and isinstance(action, str) and (action == "*" or action.endswith(":*")):
                    err(f"{where}: wildcard action {action}")
            targets = statement.get("Resource", [])
            targets = targets if isinstance(targets, list) else [targets]
            if "*" in targets and rtype != "AWS::KMS::Key" and logical_id not in exceptions["WildcardResources"]:
                err(f"{where}: Resource '*' must be recorded in WildcardResources")

    for value in walk({k: v for k, v in doc.items() if k != "Metadata"}):
        if isinstance(value, str):
            for pattern, message in HARDCODED:
                if pattern.search(value):
                    err(f"{rel}: {message}: {value[:70]}")

    if is_blueprint:
        errors.extend(check_nested(path, rel, resources))
    return errors


def check_nested(path: Path, rel: Path, resources: dict) -> list[str]:
    errors = []
    nested = 0
    for logical_id, resource in resources.items():
        if resource.get("Type") != "AWS::CloudFormation::Stack":
            continue
        nested += 1
        props = resource.get("Properties") or {}
        url = props.get("TemplateURL")
        if not isinstance(url, str) or url.startswith("http"):
            errors.append(f"{rel}: {logical_id}: TemplateURL must be a relative path")
            continue
        child_path = (path.parent / url).resolve()
        if not child_path.is_file():
            errors.append(f"{rel}: {logical_id}: {url} does not exist")
            continue
        child = plain(load(child_path))
        child_params = child.get("Parameters", {})
        passed = props.get("Parameters") or {}
        for name in passed:
            if name not in child_params:
                errors.append(f"{rel}: {logical_id}: passes unknown parameter {name}")
        for name, param in child_params.items():
            if "Default" not in param and name not in passed:
                errors.append(f"{rel}: {logical_id}: required parameter {name} not passed")
        child_outputs = child.get("Outputs", {})
        for value in walk_getatt(resources):
            target, attr = value
            if target == logical_id and attr.startswith("Outputs.") and attr[8:] not in child_outputs:
                errors.append(f"{rel}: !GetAtt {target}.{attr} is not an output of {url}")
    if nested == 0:
        errors.append(f"{rel}: a blueprint must compose at least one nested stack")
    return errors


def walk_getatt(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "Fn::GetAtt":
                parts = value if isinstance(value, list) else str(value).split(".", 1)
                if len(parts) == 2 and isinstance(parts[1], str):
                    yield parts[0], parts[1]
            else:
                yield from walk_getatt(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_getatt(value)


def templates() -> list[Path]:
    found = list((ROOT / "templates").rglob("*.yaml")) + list((ROOT / "blueprints").rglob("*.yaml"))
    return sorted(found)


def render_catalog(paths: list[Path]) -> str:
    groups: dict[str, list[tuple[str, str, str]]] = {}
    for path in paths:
        doc = plain(load(path))
        lib = doc.get("Metadata", {}).get("Library", {})
        rel = path.relative_to(ROOT).as_posix()
        groups.setdefault(lib.get("Domain", "unknown"), []).append(
            (rel, " ".join(str(lib.get("Summary", "")).split()), " ".join(str(lib.get("Cost", "")).split()))
        )
    lines = [
        "# Template catalog",
        "",
        "Generated by `scripts/check_library.py --write-catalog`. Do not edit by hand.",
        "",
        f"{len(paths)} templates.",
    ]
    for domain in sorted(groups):
        lines += ["", f"## {domain}", "", "| Template | What it creates | Cost |", "|---|---|---|"]
        for rel, summary, cost in sorted(groups[domain]):
            cell = lambda s: s.replace("|", "\\|")
            lines.append(f"| [`{rel}`](../{rel}) | {cell(summary)} | {cell(cost)} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-catalog", action="store_true")
    args = parser.parse_args()

    paths = templates()
    if not paths:
        print("no templates found", file=sys.stderr)
        return 1
    errors = [e for path in paths for e in check_template(path)]

    catalog = render_catalog(paths)
    if args.write_catalog:
        CATALOG.write_text(catalog)
    elif not CATALOG.exists() or CATALOG.read_text() != catalog:
        errors.append("docs/CATALOG.md is out of date; run scripts/check_library.py --write-catalog")

    for error in errors:
        print(error)
    print(f"{len(paths)} templates checked, {len(errors)} problems")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
