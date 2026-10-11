---
name: property-based-testing
description: >-
  Use this skill when designing or implementing property-based tests (PBT), invariant testing,
  round-trip serialization tests, or fuzz/edge-case tests for business logic and algorithms.
---

# Property-Based Testing (PBT) Guide

Property-based testing verifies that code satisfies fundamental invariants and properties across thousands of randomly generated inputs, shrinking failing cases to minimal reproductions.

## Core Property Patterns

### 1. Round-Trip Properties
- **Concept**: Applying an operation followed by its inverse returns the original value.
- **Formula**: `f_inverse(f(x)) == x`
- **Use Cases**:
  - Serialization / Deserialization (JSON, Protobuf, binary)
  - Encoding / Decoding (Base64, URL encoding)
  - Parsing / Formatting (Dates, numbers, structured templates)
  - Compression / Decompression

### 2. Invariant Properties
- **Concept**: Certain characteristics or business rules must hold true regardless of the input.
- **Use Cases**:
  - **Size / Element preservation**: Sorting or filtering should preserve elements or maintain predictable lengths.
  - **Range bounds**: Normalization produces values in `[0, 1]`, discounts never exceed 100%, balances never go negative.
  - **Ordering guarantees**: Sorted lists always satisfy `list[i] <= list[i+1]`.

### 3. Idempotence
- **Concept**: Applying an operation multiple times yields the exact same result as applying it once.
- **Formula**: `f(f(x)) == f(x)`
- **Use Cases**:
  - Deduplication, data normalization, cleanup routines, state reconciliation.

### 4. Commutativity
- **Concept**: Changing the order of operations does not change the result.
- **Formula**: `f(a, b) == f(b, a)`
- **Use Cases**:
  - Aggregations, set unions, concurrent merge operations.

### 5. Test Oracles
- **Concept**: Comparing a complex or optimized implementation against a simple, obviously correct reference implementation.
- **Use Cases**:
  - High-performance algorithm vs naive brute-force algorithm.

## Implementation Checklist
1. **Identify Properties**: Review business logic for invariants, round-trips, and idempotency.
2. **Select Domain Generator**: Use framework generators (fast-check for JS/TS, hypothesis for Python, jqwik for Java, proptest for Rust) constrained to the domain's valid input space.
3. **Verify Edge Cases**: Ensure generators cover boundaries (empty collections, 0, negative numbers, max integer, unicode, whitespace).
4. **Complement Example Tests**: PBT complements, but does not replace, specific business scenario unit tests.
