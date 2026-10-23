---
name: api-design
description: REST and GraphQL API design, documentation, and contract testing
version: 1.0.0
activation: ["openapi.yaml", "swagger.yaml", "*.graphql", "*.gql"]
tags: [api, rest, graphql, openapi, swagger]
requires_profile: full
---

# API Design Skill

## REST API Checklist
1. Use nouns for resources (`/users`, `/orders`), not verbs.
2. Use HTTP methods correctly: GET (read), POST (create), PUT/PATCH (update), DELETE.
3. Return consistent error shapes: `{"error": "message", "code": "ERROR_CODE"}`.
4. Version the API: `/api/v1/`.
5. Paginate list endpoints.

## Documentation
1. Maintain `openapi.yaml` or `swagger.yaml`.
2. Document all request/response schemas.
3. Include example values.

## Contract Testing
1. Generate client from OpenAPI spec.
2. Test against live server with `httpx` or `requests`.
3. Validate response schemas with `jsonschema`.
