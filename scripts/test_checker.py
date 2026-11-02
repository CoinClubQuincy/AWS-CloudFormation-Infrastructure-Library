#!/usr/bin/env python3
"""Prove the checker catches each kind of defect by feeding it broken copies of a valid template."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import check_library as c

SOURCE = (c.ROOT / "templates/storage/s3-bucket.yaml").read_text()
MUTANTS = {
    "tag removed": ("        - {Key: ManagedBy, Value: CloudFormation}\n", ""),
    "deletion policy removed": ("    DeletionPolicy: Retain\n", ""),
    "public access block off": ("BlockPublicAcls: true", "BlockPublicAcls: false"),
    "hardcoded ARN": ("!Ref KmsKeyArn, !Ref AWS::NoValue", "'arn:aws:kms:us-east-1:123456789012:key/x', !Ref AWS::NoValue"),
    "export renamed": ("${AWS::StackName}-BucketArn", "${AWS::StackName}-Other"),
    "physical name": ("      VersioningConfiguration:", "      BucketName: fixed\n      VersioningConfiguration:"),
    "secret parameter": ("  KmsKeyArn:\n", "  DbPassword:\n    Type: String\n    Description: x\n  KmsKeyArn:\n"),
    "wrong domain": ("Domain: storage", "Domain: nope"),
}


def main() -> int:
    path = c.ROOT / "templates/storage/_mutant.yaml"
    missed = []
    try:
        path.write_text(SOURCE)
        baseline = len(c.check_template(path))
        for name, (old, new) in MUTANTS.items():
            if old not in SOURCE:
                missed.append(f"{name}: mutation did not apply")
                continue
            path.write_text(SOURCE.replace(old, new, 1))
            found = len(c.check_template(path))
            print(f"{name:26} {found - baseline} new problem(s)")
            if found <= baseline:
                missed.append(name)
    finally:
        path.unlink(missing_ok=True)
    for name in missed:
        print(f"MISSED: {name}")
    return 1 if missed else 0


if __name__ == "__main__":
    raise SystemExit(main())
