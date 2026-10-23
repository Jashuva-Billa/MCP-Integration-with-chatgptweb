---
name: java-backend
description: Java, Maven/Gradle build, testing, and backend development workflow
version: 1.0.0
activation: ["*.java", "pom.xml", "build.gradle", "*.kt"]
tags: [java, maven, gradle, spring, junit]
requires_profile: full
---

# Java / Backend Development Skill

## Setup
1. Check Java version: `run_command("java -version")`
2. Build: `run_command("mvn compile")` or `run_command("gradle build")`

## Quality Gates
1. Compile: `run_command("mvn compile")`
2. Test: `run_tests(framework="mvn")`
3. Package: `run_command("mvn package -DskipTests")`
4. Check style: `run_command("mvn checkstyle:check")`

## Patterns
- Use JUnit 5 `@Test`, `@BeforeEach`, `@AfterEach`.
- Mock with Mockito: `@Mock`, `@InjectMocks`.
- Use `@SpringBootTest` for integration tests.
- Use `TestContainers` for database integration tests.
