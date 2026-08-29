# UpgradeGuard

Evidence based dependency upgrade and licence policy verifier for Python projects.

## The question we are answering

If a developer upgrades one important dependency, can the project still be built,
tested and distributed safely?

Most tools answer that from package metadata alone. We answer it by actually doing
the upgrade twice, in two clean environments, and comparing what really happened.

## What it does

Given a Python repository and one proposed direct dependency upgrade, UpgradeGuard:

1. builds two clean isolated environments, one with the current version and one
   with the proposed version
2. records the full direct and transitive dependency graph on both sides
3. keeps the install logs and the exact resolved package versions
4. checks dependency conflicts, known vulnerabilities and a licence policy you write
5. runs the repository's own test suite in both environments
6. reports only the failures that are new after the upgrade
7. returns Accept, Reject or Insufficient Evidence, with every reason pointing at a
   real piece of evidence

## Status

Early. This is a university software engineering project and we are still building
it. The core pipeline works end to end on our demo repository.

## Team

Gurman Singh, Madhur Tuteja, Prayag.
