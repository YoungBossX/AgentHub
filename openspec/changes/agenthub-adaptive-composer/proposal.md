# Adaptive composer and focused public copy

## Why

The user authorized applying useful desktop-agent-ui guidance to the existing UI,
then making minimal content corrections in README.md and root index.html. The
current composer has a fixed height, and the small-screen shell uses only dvh,
which does not cover a keyboard that changes only the visual viewport.

## What Changes

Grow/shrink the existing textarea with its draft and available width, retain a
bounded internal scroll area, and keep its existing IME/send/ref behavior. Fit
the narrow workbench to the unzoomed visual viewport and improve composer touch
targets/safe-area spacing. Reuse themes, surfaces, panes and evidence disclosure.
Update only a few existing public text nodes to describe the verified behavior.

## Impact

One focused frontend task plus its documentation and browser acceptance. No new
dependencies, adapters, data changes, desktop shell, API calls or benchmark claims.
Keep README structure and index.html markup/styles/scripts/assets unchanged except
the selected copy. Work in the user's current clean dev checkout; do not commit
or push. Evidence and temporary files stay in E:/Docker/AgentHub.
