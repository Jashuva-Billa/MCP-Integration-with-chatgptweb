---
name: agentic-ai-langgraph
description: Agentic AI systems, LangGraph workflows, and multi-agent orchestration
version: 1.0.0
activation: ["*.py", "agent*.py", "graph*.py"]
tags: [agent, langgraph, langchain, llm, orchestration, tools]
requires_profile: full
---

# Agentic AI and LangGraph Skill

## Graph Design Principles
1. Define clear node responsibilities (plan, execute, reflect, verify).
2. Use conditional edges for branching logic.
3. Keep state minimal — only what nodes need.
4. Handle errors explicitly; never silently swallow tool errors.

## LangGraph Workflow
1. Define `TypedDict` state schema.
2. Create `StateGraph` with nodes and edges.
3. Add tools as ToolNode.
4. Compile and stream: `graph.stream(initial_state)`.

## Safety
- Set `max_iterations` to prevent infinite loops.
- Require confirmation before destructive tool calls.
- Log all tool invocations with inputs and outputs.
- Test with mock tools before using real integrations.
