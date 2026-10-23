## ADDED Requirements

### Requirement: Consistent supplied brand artwork
The workbench SHALL use the user's supplied icon for product branding and app
metadata without changing workspace names, role icons or theme behavior.

#### Scenario: Sidebar and browser icons
- **WHEN** the workbench loads in either theme
- **THEN** its 40px sidebar mark displays the supplied artwork without distortion
- **AND** metadata supplies compact browser and Apple touch PNG icons from the same source
- **AND** the source image remains identical to the uploaded file
