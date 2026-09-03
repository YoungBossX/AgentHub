# Generated Project Dependency Pinning

## ADDED Requirements

### Requirement: Generated project direct dependencies are reviewable and stable

AgentHub SHALL write exact versions for every direct dependency in a newly
provisioned frontend `package.json` and backend `requirements.txt`. Generated
manifests SHALL NOT contain registry tags, semver ranges, wildcards, or
unversioned Python requirements. The generated frontend manifest SHALL declare
the repository's verified package-manager release.

#### Scenario: An empty selected folder is provisioned

- **WHEN** project provisioning writes the Vite React and FastAPI skeletons
- **THEN** both generated manifests contain the repository's verified exact
  direct dependency versions
- **AND** the FastAPI test client's direct dependency is declared
- **AND** Corepack selects the verified pnpm release rather than a moving
  package-manager version
- **AND** the existing approval-gated setup commands remain unchanged.

### Requirement: Existing provisioned scaffolds are not rewritten

AgentHub SHALL preserve the existing repair behavior and SHALL NOT replace a
user-owned manifest when registering a repairable AgentHub scaffold.

#### Scenario: A repairable AgentHub scaffold is applied again

- **WHEN** its metadata, frontend, backend, and documentation boundaries exist
- **THEN** target registration may be repaired
- **AND** its existing dependency manifests are not rewritten.
