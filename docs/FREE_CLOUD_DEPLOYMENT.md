# Free remote MCP deployment

The root Dockerfile prepares this server for a remote Streamable HTTP endpoint at /mcp. It runs as a non-root user, keeps runtime repository state under /tmp, and defaults to cloud mode with bearer authentication enabled.

## Required hosting environment

- MCP_DEPLOYMENT_MODE=cloud
- MCP_AUTH_ENABLED=true
- MCP_AUTH_TOKEN: set a random secret of at least 32 characters in the hosting provider's secret settings.
- MCP_ALLOWED_HOSTS: set the exact public hostname, without scheme/path/wildcards.
- MCP_PERMISSION_PROFILE=safe by default. This intentionally denies Git push and destructive file operations.
- MCP_GIT_PUSH_ENABLED=true plus MCP_PERMISSION_PROFILE=trusted_admin enables Git push; keep MCP_GIT_PUSH_REQUIRE_APPROVAL=true so pushes require a matching approved target. Use this only for a private, personal server after reviewing the broader trusted_admin profile.
- MCP_GITHUB_CLONE_ENABLED=true to enable repository cloning.
- MCP_GITHUB_ALLOWED_REPOS: comma-separated OWNER/REPOSITORY slugs.
- MCP_GITHUB_TOKEN: optional least-privilege GitHub token for private repositories.

The application refuses to start in cloud mode when authentication is disabled, the bearer token is missing/too short, or the exact host allowlist is missing or contains wildcards. Cloud mode always keeps DNS-rebinding protection enabled. Local mode preserves the existing tunnel workflow unless explicit allowed hosts are configured.

## Deploy

1. Create a free container web service with a provider that permits signup without a payment card; verify its current terms first.
2. Connect this GitHub repository and deploy from the root Dockerfile.
3. After the provider assigns a hostname, set MCP_ALLOWED_HOSTS to that exact hostname and set MCP_AUTH_TOKEN as a secret, then redeploy.
4. Add only explicitly trusted repositories to MCP_GITHUB_ALLOWED_REPOS. For example: Jashuva-Billa/MCP-Integration-with-chatgptweb.
5. Check GET /health and connect ChatGPT to https://YOUR-HOST/mcp with bearer-token authentication.

## Workspace behavior

The clone_github_repository tool only accepts HTTPS GitHub URLs that match the explicit repository allowlist. It clones to MCP_WORKSPACE_ROOT, refuses to overwrite an existing workspace, and registers the clone. GitHub becomes the durable source of truth; a free host's local workspace may disappear after sleep or restart.

Files that exist only on your PC cannot be accessed while that PC is off. Push or otherwise synchronize them to a remote repository first.

This change does not create a hosting account, deploy the container, create provider secrets, or register the connector in ChatGPT. Those steps require account access.