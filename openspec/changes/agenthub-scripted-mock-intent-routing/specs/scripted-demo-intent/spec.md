## ADDED Requirements

### Requirement: Scripted demo mutations respect the structured task target

The system SHALL select the existing login-page, primary-button copy and heading
copy mutations from their structured task targets when provided. It SHALL ignore
conflicting action keywords in instruction prose or legacy script hints. Copy
targets SHALL use a nonempty structured targetText. Missing-target legacy requests
SHALL retain their existing bounded demo behavior.

#### Scenario: Rendered metadata contains title and button words

- **WHEN** a login_page task's full instruction includes title, heading or button
- **THEN** ScriptedMock SHALL create the email/password login form
- **AND** it SHALL leave the page heading and existing primary button unchanged

#### Scenario: Button follow-up preserves the login form

- **WHEN** a dependent same-Session primary_action_button_text Task specifies targetText
- **THEN** ScriptedMock SHALL change only the deterministic primary button's text
- **AND** it SHALL preserve the existing login form and heading
- **AND** actual execution SHALL retain scope and nonempty-Diff completion checks

#### Scenario: Unsupported structured requests do not make unrelated changes

- **WHEN** an explicit target is unsupported/malformed or a copy target lacks valid text
- **THEN** ScriptedMock SHALL emit its existing mutation-failure error before writing
- **AND** it SHALL NOT silently select another mutation based on prose
