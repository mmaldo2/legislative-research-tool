---
status: pending
priority: p3
issue_id: "043"
tags: [code-review, typescript]
dependencies: []
---

# 043 - ApiError class prototype chain issue

## Problem Statement

The `ApiError` class extends `Error` but is missing the `Object.setPrototypeOf(this, ApiError.prototype)` call in its constructor. This means `instanceof ApiError` checks may fail when the project targets ES5 or when certain bundler configurations transform class inheritance. Additionally, the `status` property should be marked `readonly` to prevent accidental mutation.

## Findings

- The `ApiError` constructor at `frontend/src/lib/api.ts:21-29` extends `Error` without restoring the prototype chain.
- When TypeScript compiles `class X extends Error` to ES5, the prototype chain is broken because `Error` is a built-in. The `instanceof` operator will incorrectly return `false` for `ApiError` instances.
- The `status` property is mutable, which could lead to accidental reassignment in catch blocks.

## Proposed Solutions

1. Add `Object.setPrototypeOf(this, ApiError.prototype)` as the last line of the `ApiError` constructor.
2. Mark the `status` property as `readonly`.

Example fix:
```typescript
class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}
```

## Technical Details

- This is a well-documented TypeScript issue when extending built-in classes like `Error`, `Array`, or `Map`. See the TypeScript handbook section on extending built-ins.
- The fix is a single line addition and a `readonly` modifier, with zero behavioral change for environments where the prototype chain already works (modern ES2015+ targets).
- Without the fix, any `catch` block that uses `if (err instanceof ApiError)` could silently fall through to a generic error handler.

## Acceptance Criteria

- [ ] `Object.setPrototypeOf(this, ApiError.prototype)` added to the `ApiError` constructor
- [ ] `status` property marked as `readonly`
- [ ] `instanceof ApiError` returns `true` in both ES5 and ES2015+ compilation targets
- [ ] Existing error handling logic continues to work correctly
- [ ] TypeScript compilation passes with no errors

## Work Log

_No work performed yet._

## Resources

- `frontend/src/lib/api.ts`
- [TypeScript Breaking Changes: Extending Built-ins](https://github.com/microsoft/TypeScript/wiki/Breaking-Changes#extending-built-ins-like-error-array-and-map-may-no-longer-work)
