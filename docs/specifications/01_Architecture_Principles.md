# 01 Architecture Principles

## Mission

Build a scientific platform where users discover reagents through research intent and scientific relationships.

Primary journey:

```text
Research Goal
      ↓
Application
      ↓
Method
      ↓
Protocol
      ↓
Product
      ↓
SKU
```

Every implementation decision must preserve this model.

---

## Principle 1

Research Goal is the highest-level user entry.

---

## Principle 2

Products never exist in isolation.

Every Product must expose:

* Applications
* Methods
* Protocols
* References
* Related Products

---

## Principle 3

Knowledge Graph relationships are first-class entities.

Relationships are not hidden implementation details.

---

## Principle 4

Homepage is a Research Solution Hub.

Not a catalog homepage.

---

## Principle 5

Scientific context has higher priority than product category.

Priority:

```text
Research Goal > Application > Method > Protocol > Product Category
```

---

## Principle 6

All pages must be machine-readable.

Future systems:

* RAG
* LLM
* AI Agents
* Semantic Search

must be attachable without refactoring.
