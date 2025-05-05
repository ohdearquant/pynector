# Implementation Update: Optional Observability (Issue #3)

## Current Status

I've fixed the failing tests in the Optional Observability implementation by
addressing issues with async context managers and mocking. All tests are now
passing or skipped.

## Test Coverage Analysis

Current test coverage:

```
Name                                 Stmts   Miss  Cover
--------------------------------------------------------
src/pynector/telemetry/__init__.py      21      0   100%
src/pynector/telemetry/config.py       179     84    53%
src/pynector/telemetry/context.py       64     34    47%
src/pynector/telemetry/facade.py       118     17    86%
src/pynector/telemetry/logging.py        9      0   100%
src/pynector/telemetry/tracing.py       41      5    88%
--------------------------------------------------------
TOTAL                                  432    140    68%
```

The overall coverage is 68%, which is below the required 80%. The main issues
are in:

1. `config.py` (53% coverage)
2. `context.py` (47% coverage)

## Key Issues Identified

1. **Async Context Manager Issues**: The `AsyncSpanWrapper` class had issues
   with returning the span directly in `__aenter__` instead of returning itself,
   which caused tests to fail when trying to call methods on the returned
   object.

2. **Mocking Issues**: The tests were using `MagicMock` for async context
   managers, but `MagicMock` doesn't implement `__await__`, which is required
   for async context managers.

3. **Test Coverage**: The complex parts of the code, especially in `config.py`
   and `context.py`, are difficult to test due to dependencies on external
   libraries.

## Recommendations

1. **Use Test Containers**: For the "not available" problem, we should use test
   containers to provide mock implementations of the external dependencies
   (OpenTelemetry, structlog) during testing. This would allow us to test the
   code more thoroughly without having to skip tests.

2. **Improve Testability**: Refactor the code to make it more testable,
   especially in `config.py` and `context.py`. This could involve:
   - Breaking down complex functions into smaller, more testable functions
   - Using dependency injection to make it easier to mock dependencies
   - Creating interfaces for external dependencies to make them easier to mock

3. **Add More Tests**: Add more tests for the complex parts of the code,
   especially in `config.py` and `context.py`, to increase coverage.

## Next Steps

1. Implement test containers for the external dependencies
2. Refactor the code to improve testability
3. Add more tests to increase coverage to ≥80%
4. Update the PR with the changes

## Conclusion

The Optional Observability implementation is working, but the test coverage
needs to be improved to meet the ≥80% requirement. Using test containers and
improving the testability of the code would help achieve this goal.
