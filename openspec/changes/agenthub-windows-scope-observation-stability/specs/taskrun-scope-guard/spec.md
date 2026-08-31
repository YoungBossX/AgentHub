# Windows TaskRun Scope Observation Stability

## ADDED Requirements

### Requirement: Windows directory path observations ignore only the transient enumeration bit

The Windows scope collector SHALL normalize the undocumented `0x10000000`
`st_file_attributes` bit only for directory path observations when comparing a
bound path before and after directory enumeration. It SHALL retain exact device,
inode, file type, documented file-attribute, reparse-point, named-stream,
ordinary-file descriptor, and Git executable checks.

#### Scenario: Enumeration clears the transient Python directory bit

- **GIVEN** a newly created ordinary Windows directory whose Python path stat
  contains `0x10000000` before its first enumeration
- **WHEN** enumeration clears only that bit while device, inode, file type, and
  all documented file attributes remain unchanged
- **THEN** the directory path observation remains stable
- **AND** the directory remains represented in the complete scope snapshot.

#### Scenario: A security-relevant identity field changes

- **WHEN** a directory observation changes device, inode, file type, any other
  file-attribute bit, reparse status, or named-stream evidence
- **THEN** complete snapshot capture remains unavailable and fails closed
- **AND** the compatibility rule MUST NOT be applied to an ordinary file,
  protected file, descriptor observation, or Git executable.
