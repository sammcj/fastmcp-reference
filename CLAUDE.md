# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Repository Purpose

This is a **documentation repository** containing architectural research on FastMCP (Model Context Protocol) platform components. It contains no executable code—only research deliverables in markdown format analysing sources including official documentation, production implementations, and security articles.

**Research Focus:** How to design low-level, reusable MCP components that enable teams to build AI tools efficiently without reinventing infrastructure.

**Primary Use Case:** Reference material for building foundational MCP platform components and tools with middleware-based architecture.

---

## Document Structure

All documents follow a hierarchical structure designed for different audiences:

### Core Research Documents

1. **README.md** - Central index and research methodology overview (4-stage process: Discovery, Deep Analysis, Synthesis, Client Packaging)
2. **reference/fastmcp-executive-summary.md** - Business-focused findings for stakeholders (ROI, risks, implementation roadmap)
3. **reference/fastmcp-technical-architecture.md** - Detailed technical implementation guide for engineers (core patterns with runnable code)
4. **reference/fastmcp-patterns-anti-patterns.md** - Best practices catalogue for development teams (patterns, anti-patterns with severity ratings)
5. **reference/fastmcp-architecture-research-references.md** - Source inventory and research methodology (sources with quality ratings A/B+/B/C)
6. **reference/fastmcp-builtin-features.md** - FastMCP framework capabilities reference (what NOT to re-implement)

### Document Relationships

```
README.md (Entry Point)
├── Executive Summary (Stakeholders)
├── Technical Architecture (Platform Engineers)
│   └── Patterns & Anti-Patterns (Tool Developers)
└── Research References (Validation & Deep Dive)
```

---

## Document Versioning

**CRITICAL:** When modifying ANY document, you MUST update the version table at the bottom of README.md:

```markdown
| Document                 | Version | Last Updated    |
|--------------------------|---------|-----------------|
| Document Name            | X.Y     | 28 October 2025 |
```

**Versioning Rules:**
- Increment minor version (X.Y → X.Y+1) for content updates, additions, corrections
- Increment major version (X.Y → X+1.0) for structural changes or complete rewrites
- Always update "Last Updated" to current date

---

## Writing Standards

### Content Philosophy

These documents prioritise **technical accuracy and clarity** over marketing language:

- ❌ Avoid: "comprehensive", "enhanced", "production-ready", "seamless", "robust"
- ✅ Use: Specific technical details, trade-offs, constraints, confidence levels
- Focus on "what" and "how" over "why it's amazing"
- Include source citations and confidence levels for claims

### Structure Conventions

1. **Headers**: Use ATX-style headers (`#`, `##`, `###`)
2. **Code Blocks**: Always specify language for syntax highlighting
3. **Confidence Levels**: Mark findings with HIGH/MEDIUM/LOW confidence
4. **Source Citations**: Reference specific sources from research inventory
5. **Mermaid Diagrams**: Use consistent colour scheme (see global CLAUDE.md rules)

### Markdown Formatting

- Use **British English spelling** throughout (organise, analyse, behaviour, etc.)
- Use standard markdown lists (no emoji bullets unless user-specified)
- Keep tables readable with alignment
- Use `code formatting` for technical terms, file paths, commands

---

## Key Research Findings Summary

### High-Confidence Patterns (Use These)

Research validated through multiple authoritative sources (Quality: A, Confidence: HIGH):

1. **Middleware-Based Architecture** - Centralised cross-cutting concerns (auth, logging, rate limiting, error handling) using FastMCP's pipeline model
2. **Server Composition** - Domain-specific servers mounted/imported into platform for team autonomy and parallel development
3. **In-Memory Testing** - FastMCPTransport for rapid test execution (50-100 tests in 2-3 seconds, 1000+ tests in FastMCP repo use this)
4. **Environment Variable Configuration** - 12-factor app pattern for cloud-native deployment
5. **OAuth Integration** - Built-in enterprise authentication (Google, GitHub, Azure, WorkOS, Auth0) with zero-config client experience
6. **Connection Pooling** - Database and HTTP client pools created at startup via lifespan hooks
7. **Context-Based State Sharing** - Request-scoped state via Context, not global variables
8. **Progress Reporting** - `ctx.report_progress()` for long-running operations

### Critical Anti-Patterns (Avoid These)

Severity ratings based on impact analysis:

1. **⚠️ AI Precision Anti-Pattern (CRITICAL)** - Using LLMs for deterministic tasks (maths, validation, data format conversions). LLMs orchestrate tools; tools execute logic.
2. **⚠️ STDIO Protocol Violation (CRITICAL)** - Logging to stdout/stderr in STDIO transport mode corrupts JSON-RPC protocol stream. Always use Context logging methods.
3. **⚠️ Leaky Abstraction (CRITICAL)** - Bypassing platform abstractions to create own DB connections/HTTP clients. Loses connection pooling, observability, security controls.
4. **⚠️ State Leakage (CRITICAL)** - Global variables shared across requests causing race conditions and data leaks. Use Context for request state.
5. **⚠️ Missing Connection Cleanup (CRITICAL)** - Not closing resources leads to exhaustion. Use lifespan hooks and context managers.
6. **⚠️ Hardcoded Configuration (CRITICAL)** - Secrets in code. Use environment variables and secret managers.
7. **Fat Tools (HIGH)** - Tools with 5+ parameters or multiple modes confuse LLMs. Split into focused tools.
8. **God Servers (HIGH)** - 50+ tools in one server. Split by domain using composition patterns.
9. **Sync I/O in Async (HIGH)** - `time.sleep()`, `requests`, `open()` block event loop. Use `asyncio.sleep()`, `httpx`, `aiofiles`.
10. **SSE Mode** - SSE mode has been deprecated in favour of streamable HTTP.

---

## Common Tasks

### Updating Research Documents

**Standard Workflow:**
1. Read the relevant document to understand current content and structure
2. Make targeted changes (avoid wholesale rewrites unless document is fundamentally flawed)
3. Update version number (minor increment X.Y → X.Y+1 for content updates) and date in README.md version table
4. Verify internal cross-references still work (especially links between documents)
5. Check consistency with related documents (patterns appear in both Technical Architecture and Patterns Catalogue)
6. Verify code examples still follow current best practices

**Version Increment Rules:**
- **Minor (X.Y → X.Y+1):** Content updates, additions, corrections, new sections
- **Major (X.Y → X+1.0):** Structural changes, complete rewrites, new document organisation

### Adding New Research

**Integration Workflow:**
1. Determine appropriate document:
   - **Technical Architecture:** Implementation patterns with detailed code examples
   - **Patterns Catalogue:** Additional patterns or anti-patterns with trade-offs
   - **Executive Summary:** Business impact or strategic findings
   - **Built-in Features:** New FastMCP framework capabilities
2. Add new section following existing structure (Intent, Problem, Solution, Code Example, Trade-offs, When to Use, Sources, Confidence)
3. Include confidence level (HIGH/MEDIUM/LOW) based on source quality and corroboration
4. Add source citations with quality ratings (A/B+/B/C)
5. Update README.md table of contents if adding major new sections
6. Update version table in README.md with incremented version and current date

**Source Quality Guidelines:**
- **A (HIGH confidence):** Official docs, protocol specs, primary repos, maintainer statements
- **B+ (MEDIUM-HIGH):** Production guides, security implementations, established patterns
- **B (MEDIUM):** Best practices articles, architectural analyses, community patterns
- **C (LOW-MEDIUM):** Community implementations, blog posts, single-source claims

### Extracting Information for Implementation

This repository is designed for **extraction**, not execution. When asked to "use" these patterns:

1. **Locate the pattern:** Check Technical Architecture (detailed) or Patterns Catalogue (overview)
2. **Extract code examples:** Copy runnable code, note dependencies and prerequisites
3. **Check confidence level:** HIGH patterns are production-ready, MEDIUM may need validation, LOW requires prototyping
4. **Note trade-offs:** Every pattern has advantages and disadvantages documented
5. **Verify built-ins:** Check `reference/fastmcp-builtin-features.md` to avoid reimplementing existing functionality
6. **Cite source:** Reference document section and confidence level

**Example Extraction:**
```
User: "How should I implement authentication?"
Response: "Use OAuth with built-in providers (see Technical Architecture: Authentication & Authorisation, Confidence: HIGH).
FastMCP provides GoogleProvider, GitHubProvider, etc. with zero-config client experience.
Code example at fastmcp-technical-architecture.md:467-486.
Don't implement custom OAuth flow - use built-in providers from reference/fastmcp-builtin-features.md."
```

### Verifying Information

**Validation Workflow:**
1. Check confidence level in relevant document (look for HIGH/MEDIUM/LOW tags)
2. Review source inventory in `reference/fastmcp-architecture-research-references.md`
3. Note source quality rating (A = authoritative, B+ = high-quality secondary, B = solid secondary, C = community)
4. Check number of corroborating sources (1 source = LOW confidence, 2-3 = MEDIUM, 3+ authoritative = HIGH)
5. Identify any research gaps or limitations (explicitly documented in findings)

**Red Flags for Low Confidence:**
- Single source (no corroboration)
- Community source only (no official docs)
- Marked as "requires prototyping" or "limited documented patterns"
- Flagged in research gaps section

---

## Architecture Principles

These principles underpin all recommendations in the research:

1. **Favour Simplicity** - Minimal abstractions unless complexity warrants them
2. **Team Autonomy** - Platform provides infrastructure, teams own business logic
3. **Security by Default** - Centralised enforcement of auth, rate limiting, SSRF prevention
4. **Fast Feedback Loops** - In-memory testing for rapid development
5. **Cloud-Native** - Configuration via environment variables, stateless design

---

## FastMCP Version Context

Research based on **FastMCP v2.9.0+** (October 2025).

**Important Version Notes:**
- FastMCP v2.0+ includes middleware framework (critical feature for cross-cutting concerns)
- OAuth integration available (Google, GitHub, Azure, WorkOS, Auth0, Descope)
- Built-in logging middleware available (LoggingMiddleware, StructuredLoggingMiddleware)
- Server composition patterns (mount/import) available
- Tag-based filtering and enable/disable features available
- Runtime dependency functions (`get_context()`) available
- Version pinning strongly recommended for production

**Breaking Change Risk:** FastMCP is in v2.x phase with active development. Expect API changes with major release updates. Pin versions and test thoroughly before upgrading.

---

## Anti-Pattern Severity Ratings

When reviewing code against anti-patterns:

| Severity     | Impact                                     | Action Required               |
|--------------|--------------------------------------------|-------------------------------|
| **CRITICAL** | Security risk, protocol violation          | Fix immediately, blocks merge |
| **HIGH**     | Performance issue, maintainability problem | Fix before production         |
| **MEDIUM**   | Code smell, tech debt                      | Plan refactoring              |
| **LOW**      | Stylistic concern                          | Address in next iteration     |

**CRITICAL Anti-Patterns:**
- AI Precision Anti-Pattern (LLMs for deterministic tasks)
- STDIO Protocol Violation (stdout/stderr corruption)
- Missing Auth Middleware (security bypass)
- Hardcoded Credentials (secrets in code)

---

## Reference Implementation Status

**When asked about implementation:**
- Reference patterns from Technical Architecture document
- Note that reference package is still in planning phase
- Suggest prototyping based on documented patterns

---

## Document Maintenance

### Regular Reviews

Documents should be reviewed quarterly or when:
- FastMCP releases major version (v3.0, etc.)
- New architectural patterns emerge from production use
- Research gaps are filled with new information
- Anti-patterns identified through real-world experience

### Deprecation Process

When patterns become outdated:
1. Offer to remove them to the user
2. Explain why pattern is deprecated
3. Link to replacement pattern or updated guidance
4. Update version table in README.md

---

## Getting Help

### For Questions About Research

- **Confidence Levels**: Check document section for HIGH/MEDIUM/LOW rating
- **Source Validation**: Review `reference/fastmcp-architecture-research-references.md`
- **Research Gaps**: Identified in Source Inventory document
- **Methodology**: Described in README.md

### For Implementation Guidance

- **Platform Engineers**: Start with Technical Architecture document
- **Tool Developers**: Start with Patterns & Anti-Patterns Catalogue
- **Stakeholders**: Start with Executive Summary
- **Validation**: Cross-reference patterns against Source Inventory

---

## FastMCP Built-In Features Reference

**Critical for Implementation:** Before adding dependencies, check `reference/fastmcp-builtin-features.md` to avoid reimplementing existing functionality.

### What FastMCP Already Provides

**Logging:**
- `LoggingMiddleware` (human-readable)
- `StructuredLoggingMiddleware` (JSON for production)
- Context logging methods (`ctx.debug()`, `ctx.info()`, `ctx.warning()`, `ctx.error()`)
- **Don't add:** structlog, loguru, custom logging libraries

**Middleware (Built-In):**
- `TimingMiddleware` (performance monitoring)
- `RateLimitingMiddleware` / `SlidingWindowRateLimitingMiddleware`
- `ResponseCachingMiddleware` (with multiple storage backends)
- `ErrorHandlingMiddleware`
- `ToolInjectionMiddleware`, `PromptToolMiddleware`, `ResourceToolMiddleware`

**Error Handling:**
- Complete exception hierarchy (`ToolError`, `ResourceError`, `ValidationError`, `ClientError`, etc.)
- Protocol-compliant error responses
- Automatic error transformation

**Testing:**
- `FastMCPTransport` for in-memory testing
- Full client/server test infrastructure
- Snapshot testing support (`inline-snapshot`)
- Flexible assertions (`dirty-equals`)

**Authentication:**
- OAuth providers (Google, GitHub, Azure, WorkOS, Auth0, Descope)
- JWT/OIDC verification
- Static token verifier
- Zero-config client flows

**Server Composition:**
- `mount()` (live linking for dynamic tools)
- `import_server()` (static composition for performance)
- Prefix-based namespacing
- Middleware inheritance rules

**Storage Backends:**
- In-memory, Disk, Redis, DynamoDB
- Pluggable `KeyValueStore` interface

**The Rule:** If it's in `reference/fastmcp-builtin-features.md`, don't re-implement it. Use the built-in.

---

## Notes for Claude Code

When working in this repository:

1. **Preserve technical accuracy** - Verify claims against source inventory in `reference/fastmcp-architecture-research-references.md` and if you can't - search online for authoritative sources
2. **Maintain consistency** - Cross-check related sections when updating (especially patterns between Technical Architecture and Patterns & Anti-Patterns)
3. **Update version table** - Never forget to update README.md version table after any document changes
4. **British English** - Honour spelling conventions (organise, analyse, behaviour, colour)
5. **No marketing language** - Avoid "comprehensive", "enhanced", "production-ready", "seamless". Keep tone technical and precise.
6. **Check built-in features** - Before suggesting new dependencies, verify against `reference/fastmcp-builtin-features.md`
7. **FastMCP examples** - The FastMCP project has a number of example implementations, if you have the directory `tmp_fastmcp_repo_clone` available in this project, it's a local copy of the FastMCP GitHub repository. You can refer to it for code examples and implementation patterns (`./tmp_fastmcp_repo_clone/examples/`) - otherwise you can reference examples if you need them online from https://github.com/jlowin/fastmcp/tree/main/examples
8. **Never run kill -9 python** - It's too broad and could risk killing other processes.
9. **Ensure you use the latest package versions** - Always use your tools to check that the package versions you're referencing (e.g. in pyproject.toml, requirements.txt etc.) are the latest stable releases available. For the main Python version we should target the latest stable Python (3.14.0 at the time this was written) but support Python 3.12+.
10. **UV & Virtual Environments** - If you are writing or running any Python code in this project, always use a virtual environment in .env to manage dependencies and avoid conflicts with system-wide packages. You should always use the `uv` tool for managing python versions and virtual environments.

---

## Quick Reference: Pattern Lookup

When asked about common implementation questions:

| Question                            | Document               | Section                                    | Confidence   |
|-------------------------------------|------------------------|--------------------------------------------|--------------|
| How to test tools?                  | Technical Architecture | Pattern 1: In-Memory Testing               | HIGH         |
| How to handle auth?                 | Technical Architecture | Authentication & Authorisation             | HIGH         |
| How to log properly?                | Built-in Features      | Logging Infrastructure                     | HIGH         |
| How to avoid stdout issues?         | Built-in Features      | STDIO Transport Warning                    | HIGH         |
| How to compose servers?             | Technical Architecture | Pattern 3: Server Composition              | HIGH         |
| How to handle errors?               | Technical Architecture | Pattern 6: Error Handling                  | HIGH         |
| How to manage config?               | Technical Architecture | Pattern 4: Environment Variables           | MEDIUM-HIGH  |
| How to pool connections?            | Technical Architecture | Pattern 7: Connection Pooling              | MEDIUM-HIGH  |
| How to handle retries?              | Patterns Catalogue     | Pattern 11: Retry with Exponential Backoff | MEDIUM       |
| How to implement multi-tenancy?     | Patterns Catalogue     | Pattern 15: Multi-Tenancy                  | MEDIUM       |
| Should I use LLMs for calculations? | Patterns Catalogue     | Anti-Pattern 1: AI Precision               | HIGH (DON'T) |
| Can I use global variables?         | Patterns Catalogue     | Anti-Pattern 6: State Leakage              | HIGH (DON'T) |
| Can I use `requests` library?       | Patterns Catalogue     | Anti-Pattern 7: Sync I/O                   | HIGH (DON'T) |

---

**Last Updated:** 28 October 2025
**Document Version:** 1.1
