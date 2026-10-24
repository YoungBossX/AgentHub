# Chat interaction refinement

## Why

The user specified six concrete refinements to the current chat workspace:
Chinese IME safety, intentional scrolling, a single outline layer, nested radius
geometry, cancellable pane resizing and extension-preserving filenames.

## What Changes

Implement those requirements in the existing composer, conversation scroller,
workbench layout and file labels. Retain current palettes, accessibility,
session isolation, evidence semantics and mobile overlays.

## Impact

Frontend only. No dependencies, data migration, provider calls, permission
changes, commit or push. Tests and temporary browser evidence stay in E:\Docker.

Delivery follow-up authorized by the user: commit/push to `dev`, follow that
exact commit's CI and repair failures. One existing backend supervisor-generation
test may change its startup synchronization budget; runtime behavior, ownership
assertions, dependencies and data remain unchanged.
