## ADDED Requirements

### Requirement: Uploaded files are bounded and belong to one Session
The system SHALL accept supported text, PDF and raster-image bytes with bounded
validation and SHALL bind them atomically to messages in their owning Session.

#### Scenario: Valid attachment is sent
- **WHEN** a user uploads a supported file and sends a message containing its ID
- **THEN** its immutable content and metadata are bound to that message
- **AND** refresh and backend restart preserve its preview/download and identity

#### Scenario: Untrusted or stale upload reference
- **WHEN** input is oversized, invalid, outside the format limits, from another
  Session, deleted, duplicated or already bound to another message
- **THEN** the request is rejected before creating a misleading task
- **AND** no arbitrary host path, executable content or partial message binding is accepted

### Requirement: Attachment content reaches the chosen Agent honestly
The system SHALL include bounded text and actual supported image input in new
planning/execution calls, with provenance and omission evidence.

#### Scenario: Task depends on attachment-only information
- **WHEN** the user asks a supported native Agent to act on an uploaded file/image
- **THEN** the provider receives its content through a real text/image transport
- **AND** a fresh result demonstrates that content was used
- **AND** existing worktree, tool permission and completion checks still apply

#### Scenario: Attachment cannot be interpreted
- **WHEN** extraction or provider capability cannot satisfy the request
- **THEN** the user sees the limitation or failure explicitly
- **AND** a scripted fallback cannot masquerade as attachment understanding

#### Scenario: Attachment content is malicious or unrelated
- **WHEN** a file contains instruction-like text or a caller forges context references
- **THEN** attachment content remains untrusted reference data
- **AND** it cannot expand tools, file scope or cross-Session access

### Requirement: Attachment UI handles asynchronous work safely
The composer SHALL expose upload, error, remove and sent states while preserving
the correct Session association.

#### Scenario: Session changes during upload
- **WHEN** an earlier Session's upload finishes after the user switches conversations
- **THEN** it cannot become an attachment on the new Session's message
- **AND** failure or cancellation leaves the composer usable
