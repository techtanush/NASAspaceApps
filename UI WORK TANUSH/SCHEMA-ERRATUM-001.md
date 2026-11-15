# Imagery schema erratum001 — nullable relief path

The shared planning schema declares relief_path as string or null. Its traversal exclusion used `not: {pattern: ...}` without a string type guard. JSON Schema pattern does not constrain null; the enclosing not therefore rejected an intentionally absent relief. The correction adds type:string inside that not so null remains valid and string traversal remains forbidden.

This is a narrow integration-owner correction, not a new capability or a relaxation of source, checksum, attribution or no-data requirements. Real albedo imagery must never be relabelled as an elevation texture to satisfy a schema. Surface path validation is unchanged. Version1.0 semantics remain the documented optional relief path.

Tanush records the change as an isolated commit; Aradhya can cherry-pick this small schema-only erratum if using the planning schema before full integration. Runtime and planning copies are tested for equality. Tests cover null, legitimate relative path, traversal and external URL.
