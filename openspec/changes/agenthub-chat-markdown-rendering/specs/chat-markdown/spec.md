## ADDED Requirements

### Requirement: Rich ordinary chat messages
The UI SHALL render Markdown headings, emphasis, nested lists, tables, task
lists, links and code blocks in ordinary chat while preserving stored content,
quoting and whole-message copying. Code blocks SHALL have independent copying.

#### Scenario: Agent returns a formatted answer
- **WHEN** an ordinary message contains Markdown and fenced code
- **THEN** it displays structured readable content in light and dark themes
- **AND** code copying excludes fences and UI labels and reports its outcome

#### Scenario: Narrow viewport or unfinished streamed content
- **WHEN** a message has a wide table, long code line or unfinished code fence
- **THEN** it remains readable without causing page-wide horizontal overflow
- **AND** later updates and reload retain the correct message content

### Requirement: Untrusted content remains inert
The UI SHALL NOT execute embedded HTML, scripts or unsafe navigation protocols,
and SHALL NOT fetch remote Markdown images without an explicit user action.

#### Scenario: Hostile content or denied clipboard
- **WHEN** a message contains executable HTML, an unsafe link or clipboard access fails
- **THEN** the UI shows inert content or an explicit failure without script execution

#### Scenario: Oversized content
- **WHEN** a message exceeds the Markdown parsing limit
- **THEN** all original text remains available in a labelled plain-text fallback
