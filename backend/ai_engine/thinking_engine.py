"""Thinking Simulation Engine — Graph-Based Cognitive Reasoning Simulator.

A LangGraph StateGraph pipeline that simulates structured reasoning at three
cognitive levels (beginner, intermediate, expert). Reasoning is represented as
GRAPHS (nodes + edges + decisions), not plain text.  Cognitive profiles act as
hard generation constraints, strategies are generated during creation (not
tagged post-hoc), and comparison is structural (graph shape, strategy
distribution, abstraction flow) — never descriptive.

Pipeline order (NON-NEGOTIABLE — 8 nodes):
    START → cognitive_profile_generator → parallel_reasoning_generator
    → reasoning_graph_builder → strategy_constrained_generator
    → abstraction_analyzer → structural_comparator
    → (if student exists) student_graph_converter → gap_generator → END

Tech stack: LangGraph StateGraph + LLM API (Groq/OpenAI) — nothing else.
"""

import os
import json
import re
import uuid
from typing import TypedDict, Optional

from langgraph.graph import StateGraph, START, END


# ---------------------------------------------------------------------------
# Constants — cognitive constraint rules
# ---------------------------------------------------------------------------

BEGINNER_ALLOWED_OPS = ["identify", "recall", "substitute", "compute"]
BEGINNER_FORBIDDEN_OPS = ["transform", "reframe", "abstract", "optimize", "reduce"]
INTERMEDIATE_ALLOWED_OPS = ["analyze", "classify", "apply_rule", "decompose", "verify", "synthesize"]
INTERMEDIATE_LIMITED_OPS = ["transform"]
INTERMEDIATE_FORBIDDEN_OPS = ["optimize"]
EXPERT_REQUIRED_OPS = ["transform", "reframe", "abstract", "reduce", "optimize"]

VALID_STRATEGY_TYPES = {"direct_application", "rule_based", "transformation", "reduction", "optimization"}
VALID_ABSTRACTION_LEVELS = {"LOW", "MEDIUM", "HIGH"}
ABSTRACTION_SCORES = {"LOW": 1.0, "MEDIUM": 2.0, "HIGH": 3.0}

VALID_RELATION_TYPES = {"derives", "transforms", "simplifies"}


# ---------------------------------------------------------------------------
# Shared State — every node reads from / writes to this TypedDict
# ---------------------------------------------------------------------------

class ThinkingState(TypedDict):
    """Shared state flowing through every node in the thinking simulation graph.

    All nodes MUST read/write from this shared state.
    """

    # Injected dependencies
    _llm_client: object

    # Input
    problem: str
    student_answer: str  # optional

    # Pipeline data (each field written by exactly one node)
    cognitive_profiles: list[dict]      # written by cognitive_profile_generator
    reasoning_graphs: list[dict]        # written by parallel_reasoning_generator, refined by graph_builder
    strategy_distributions: list[dict]  # written by strategy_constrained_generator
    abstraction_data: list[dict]        # written by abstraction_analyzer
    comparison_results: dict            # written by structural_comparator
    student_graph: dict                 # written by student_graph_converter (conditional)
    gap_analysis: list[dict]            # written by gap_generator
    validation_passed: bool             # written by reasoning_graph_builder
    validation_notes: list[str]         # written by reasoning_graph_builder


# ---------------------------------------------------------------------------
# LLM Helper
# ---------------------------------------------------------------------------

def _llm_call(llm_client, prompt: str, max_tokens: int = 2048) -> str:
    """Make a single LLM call. Returns empty string on failure."""
    if not llm_client:
        return ""
    try:
        response = llm_client.chat.completions.create(
            model=os.environ.get("LLM_MODEL", "llama3-8b-8192"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return ""


def _parse_json(text: str, fallback=None):
    """Extract and parse JSON from LLM response text."""
    if not text:
        return fallback
    for pattern in [r'\{.*\}', r'\[.*\]']:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except (json.JSONDecodeError, ValueError):
                continue
    return fallback


# ---------------------------------------------------------------------------
# Node 1: Cognitive Profile Generator — outputs constraint rules
# ---------------------------------------------------------------------------

def cognitive_profile_generator_node(state: ThinkingState) -> dict:
    """Generate 3 cognitive profiles with strict constraint rules.

    Profiles are NOT descriptions — they are hard constraints that control
    what operations, abstraction levels, and strategies are allowed during
    reasoning generation.

    Reads: problem, _llm_client
    Writes: cognitive_profiles
    """
    problem = state["problem"]
    llm_client = state.get("_llm_client")

    profiles = []

    if llm_client:
        prompt = (
            "Generate exactly 3 cognitive reasoning profiles for this problem. "
            "Do NOT solve the problem.\n\n"
            f"Problem: {problem}\n\n"
            "Return a JSON array with 3 objects. Each MUST have:\n"
            '- "level": "beginner" | "intermediate" | "expert"\n'
            '- "description": how this level approaches the problem\n'
            '- "characteristics": array of 3-4 traits\n\n'
            "Constraints:\n"
            "- Beginner: ONLY direct formula usage, no transformations, linear reasoning\n"
            "- Intermediate: Rule application, decomposition, limited transformation\n"
            "- Expert: MUST use transformation/reduction, high abstraction, efficiency\n\n"
            "JSON array:"
        )
        result = _parse_json(_llm_call(llm_client, prompt), None)
        if isinstance(result, list) and len(result) >= 3:
            for p in result[:3]:
                level = p.get("level", "unknown")
                if level in ("beginner", "intermediate", "expert"):
                    profiles.append({
                        "level": level,
                        "description": p.get("description", ""),
                        "characteristics": p.get("characteristics", []),
                    })

    # Always enforce 3 profiles with strict constraints
    profile_map = {p["level"]: p for p in profiles}

    if "beginner" not in profile_map:
        profile_map["beginner"] = {
            "level": "beginner",
            "description": "Applies formulas directly without transformation. "
            "Linear, surface-level reasoning with no assumption checking.",
            "characteristics": [
                "Direct formula usage",
                "No transformations",
                "Linear reasoning",
                "No assumption checking",
            ],
        }
    if "intermediate" not in profile_map:
        profile_map["intermediate"] = {
            "level": "intermediate",
            "description": "Applies rules step-by-step with moderate decomposition. "
            "Handles standard variations with limited abstraction.",
            "characteristics": [
                "Step-by-step rule application",
                "Moderate decomposition",
                "Handles standard variations",
                "Limited abstraction",
            ],
        }
    if "expert" not in profile_map:
        profile_map["expert"] = {
            "level": "expert",
            "description": "Reframes the problem, uses transformation and reduction. "
            "High abstraction with optimal reasoning paths.",
            "characteristics": [
                "Problem reframing",
                "Transformation and reduction",
                "High abstraction",
                "Optimal reasoning path",
            ],
        }

    # Attach constraint rules to each profile
    final_profiles = []
    for level in ["beginner", "intermediate", "expert"]:
        p = profile_map[level]
        if level == "beginner":
            p["allowed_operations"] = BEGINNER_ALLOWED_OPS
            p["forbidden_operations"] = BEGINNER_FORBIDDEN_OPS
            p["max_abstraction"] = "LOW"
        elif level == "intermediate":
            p["allowed_operations"] = INTERMEDIATE_ALLOWED_OPS
            p["forbidden_operations"] = INTERMEDIATE_FORBIDDEN_OPS
            p["max_abstraction"] = "MEDIUM"
        else:
            p["allowed_operations"] = EXPERT_REQUIRED_OPS
            p["forbidden_operations"] = []
            p["max_abstraction"] = "HIGH"
        final_profiles.append(p)

    return {"cognitive_profiles": final_profiles}


# ---------------------------------------------------------------------------
# Node 2: Parallel Reasoning Generator — generates structured graphs
# ---------------------------------------------------------------------------

def parallel_reasoning_generator_node(state: ThinkingState) -> dict:
    """Generate 3 structurally divergent reasoning graphs under profile constraints.

    Each profile produces a graph with different step_count, operation_types,
    and abstraction_levels. Reasoning is data-structure-first.

    Reads: problem, cognitive_profiles, _llm_client
    Writes: reasoning_graphs
    """
    problem = state["problem"]
    profiles = state["cognitive_profiles"]
    llm_client = state.get("_llm_client")

    reasoning_graphs = []

    for profile in profiles:
        level = profile["level"]
        allowed_ops = profile.get("allowed_operations", [])
        forbidden_ops = profile.get("forbidden_operations", [])
        max_abs = profile.get("max_abstraction", "LOW")

        if llm_client:
            prompt = (
                f"Simulate how a {level}-level thinker reasons about this problem.\n"
                "Do NOT solve the problem. Show the REASONING STRUCTURE as a graph.\n\n"
                f"Problem: {problem}\n\n"
                f"Constraints for {level} level:\n"
                f"- Allowed operations: {', '.join(allowed_ops)}\n"
                f"- Forbidden operations: {', '.join(forbidden_ops) if forbidden_ops else 'none'}\n"
                f"- Max abstraction level: {max_abs}\n\n"
                "Return a JSON object with:\n"
                '- "nodes": array of step objects, each with:\n'
                '  - "step_id": unique id (e.g. "b1")\n'
                '  - "operation_type": one of the allowed operations\n'
                '  - "concept_used": concept or rule applied\n'
                '  - "input": what this step takes\n'
                '  - "output": what this step produces\n'
                '  - "reasoning": why this step was taken\n'
                f'  - "abstraction_level": "LOW", "MEDIUM", or "HIGH" (max: {max_abs})\n'
                '  - "strategy_type": "direct_application", "rule_based", "transformation", "reduction", or "optimization"\n'
                '- "edges": array of edge objects, each with:\n'
                '  - "from_step_id": source step\n'
                '  - "to_step_id": target step\n'
                '  - "relation_type": "derives", "transforms", or "simplifies"\n'
                '- "decisions": array of decision objects, each with:\n'
                '  - "decision_point": description\n'
                '  - "alternatives_considered": array of strings\n'
                '  - "chosen_path_reason": string\n\n'
                f"Generate {'3-4' if level == 'beginner' else '4-5' if level == 'intermediate' else '3-5'} nodes.\n"
                "JSON object:"
            )
            result = _parse_json(_llm_call(llm_client, prompt, 2048), None)
            if isinstance(result, dict) and "nodes" in result:
                graph = _build_graph_from_llm(result, level, max_abs, allowed_ops, forbidden_ops)
                reasoning_graphs.append(graph)
                continue

        # Fallback: deterministic rule-based graph
        reasoning_graphs.append(_build_fallback_graph(level, problem, max_abs))

    return {"reasoning_graphs": reasoning_graphs}


def _build_graph_from_llm(result: dict, level: str, max_abs: str,
                          allowed_ops: list, forbidden_ops: list) -> dict:
    """Build a reasoning graph from LLM output, enforcing constraints."""
    abs_order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
    max_abs_val = abs_order.get(max_abs, 3)

    nodes = []
    for s in result.get("nodes", []):
        abs_level = s.get("abstraction_level", "LOW").upper()
        if abs_level not in VALID_ABSTRACTION_LEVELS:
            abs_level = "LOW"
        # Enforce max abstraction constraint
        if abs_order.get(abs_level, 1) > max_abs_val:
            abs_level = max_abs

        strategy = s.get("strategy_type", "direct_application")
        if strategy not in VALID_STRATEGY_TYPES:
            strategy = "direct_application"

        op_type = s.get("operation_type", "identify")
        # Enforce forbidden operations
        if op_type in forbidden_ops:
            if level == "beginner":
                op_type = "compute"
            else:
                op_type = "apply_rule"

        nodes.append({
            "step_id": s.get("step_id", str(uuid.uuid4())[:8]),
            "operation_type": op_type,
            "concept_used": s.get("concept_used", ""),
            "input": s.get("input", ""),
            "output": s.get("output", ""),
            "reasoning": s.get("reasoning", ""),
            "abstraction_level": abs_level,
            "strategy_type": strategy,
        })

    edges = []
    node_ids = {n["step_id"] for n in nodes}
    for e in result.get("edges", []):
        rel = e.get("relation_type", "derives")
        if rel not in VALID_RELATION_TYPES:
            rel = "derives"
        from_id = e.get("from_step_id", "")
        to_id = e.get("to_step_id", "")
        if from_id in node_ids and to_id in node_ids:
            edges.append({
                "from_step_id": from_id,
                "to_step_id": to_id,
                "relation_type": rel,
            })

    # Auto-generate sequential edges if LLM didn't provide valid ones
    if len(edges) < len(nodes) - 1:
        edges = []
        for i in range(len(nodes) - 1):
            rel = "derives"
            next_node = nodes[i + 1]
            if next_node["operation_type"] in ("transform", "reframe", "abstract"):
                rel = "transforms"
            elif next_node["operation_type"] in ("reduce", "simplify"):
                rel = "simplifies"
            edges.append({
                "from_step_id": nodes[i]["step_id"],
                "to_step_id": next_node["step_id"],
                "relation_type": rel,
            })

    decisions = []
    for d in result.get("decisions", []):
        if isinstance(d, dict):
            decisions.append({
                "decision_point": d.get("decision_point", ""),
                "alternatives_considered": d.get("alternatives_considered", []),
                "chosen_path_reason": d.get("chosen_path_reason", ""),
            })

    return {
        "level": level,
        "nodes": nodes,
        "edges": edges,
        "decisions": decisions,
    }


def _build_fallback_graph(level: str, problem: str, max_abs: str) -> dict:
    """Build a deterministic fallback reasoning graph."""
    problem_snippet = problem[:100]

    if level == "beginner":
        nodes = [
            {"step_id": "b1", "operation_type": "identify", "concept_used": "problem recognition",
             "input": problem_snippet, "output": "Identified problem type",
             "reasoning": "Read the problem statement directly",
             "abstraction_level": "LOW", "strategy_type": "direct_application"},
            {"step_id": "b2", "operation_type": "recall", "concept_used": "formula recall",
             "input": "Problem type", "output": "Retrieved standard formula",
             "reasoning": "Recalled the most common formula for this type",
             "abstraction_level": "LOW", "strategy_type": "direct_application"},
            {"step_id": "b3", "operation_type": "substitute", "concept_used": "direct substitution",
             "input": "Values from problem", "output": "Substituted values",
             "reasoning": "Plugged values directly into formula",
             "abstraction_level": "LOW", "strategy_type": "direct_application"},
            {"step_id": "b4", "operation_type": "compute", "concept_used": "arithmetic",
             "input": "Substituted expression", "output": "Numerical result",
             "reasoning": "Performed basic computation",
             "abstraction_level": "LOW", "strategy_type": "direct_application"},
        ]
        edges = [
            {"from_step_id": "b1", "to_step_id": "b2", "relation_type": "derives"},
            {"from_step_id": "b2", "to_step_id": "b3", "relation_type": "derives"},
            {"from_step_id": "b3", "to_step_id": "b4", "relation_type": "derives"},
        ]
        decisions = [
            {"decision_point": "Selected standard formula",
             "alternatives_considered": ["No alternatives considered"],
             "chosen_path_reason": "Used the first formula that came to mind"},
        ]
    elif level == "intermediate":
        nodes = [
            {"step_id": "i1", "operation_type": "analyze", "concept_used": "problem decomposition",
             "input": problem_snippet, "output": "Identified sub-problems",
             "reasoning": "Broke the problem into manageable parts",
             "abstraction_level": "LOW", "strategy_type": "rule_based"},
            {"step_id": "i2", "operation_type": "classify", "concept_used": "pattern matching",
             "input": "Sub-problems", "output": "Matched to known patterns",
             "reasoning": "Recognized standard problem patterns",
             "abstraction_level": "MEDIUM", "strategy_type": "rule_based"},
            {"step_id": "i3", "operation_type": "apply_rule", "concept_used": "rule-based reasoning",
             "input": "Matched patterns", "output": "Applied appropriate rules",
             "reasoning": "Selected and applied relevant rules",
             "abstraction_level": "MEDIUM", "strategy_type": "rule_based"},
            {"step_id": "i4", "operation_type": "verify", "concept_used": "consistency check",
             "input": "Intermediate results", "output": "Verified intermediate steps",
             "reasoning": "Checked consistency of intermediate results",
             "abstraction_level": "MEDIUM", "strategy_type": "rule_based"},
            {"step_id": "i5", "operation_type": "synthesize", "concept_used": "integration",
             "input": "Verified sub-results", "output": "Combined result",
             "reasoning": "Combined sub-problem results",
             "abstraction_level": "MEDIUM", "strategy_type": "rule_based"},
        ]
        edges = [
            {"from_step_id": "i1", "to_step_id": "i2", "relation_type": "derives"},
            {"from_step_id": "i2", "to_step_id": "i3", "relation_type": "derives"},
            {"from_step_id": "i3", "to_step_id": "i4", "relation_type": "derives"},
            {"from_step_id": "i4", "to_step_id": "i5", "relation_type": "derives"},
        ]
        decisions = [
            {"decision_point": "Chose decomposition strategy",
             "alternatives_considered": ["Direct application", "Pattern matching"],
             "chosen_path_reason": "Decomposition enables systematic rule application"},
            {"decision_point": "Selected matching rules",
             "alternatives_considered": ["General formula", "Specific rule set"],
             "chosen_path_reason": "Specific rules are more applicable to this problem type"},
        ]
    else:  # expert
        nodes = [
            {"step_id": "e1", "operation_type": "reframe", "concept_used": "problem reframing",
             "input": problem_snippet, "output": "Reframed problem representation",
             "reasoning": "Transformed problem into a more tractable form",
             "abstraction_level": "HIGH", "strategy_type": "transformation"},
            {"step_id": "e2", "operation_type": "abstract", "concept_used": "abstraction",
             "input": "Reframed problem", "output": "Abstract structure identified",
             "reasoning": "Identified underlying abstract structure",
             "abstraction_level": "HIGH", "strategy_type": "transformation"},
            {"step_id": "e3", "operation_type": "reduce", "concept_used": "reduction",
             "input": "Abstract structure", "output": "Simplified representation",
             "reasoning": "Reduced problem complexity via transformation",
             "abstraction_level": "HIGH", "strategy_type": "reduction"},
            {"step_id": "e4", "operation_type": "optimize", "concept_used": "optimization",
             "input": "Simplified form", "output": "Optimal path identified",
             "reasoning": "Found the most efficient reasoning path",
             "abstraction_level": "HIGH", "strategy_type": "optimization"},
        ]
        edges = [
            {"from_step_id": "e1", "to_step_id": "e2", "relation_type": "transforms"},
            {"from_step_id": "e2", "to_step_id": "e3", "relation_type": "simplifies"},
            {"from_step_id": "e3", "to_step_id": "e4", "relation_type": "derives"},
        ]
        decisions = [
            {"decision_point": "Chose to reframe problem",
             "alternatives_considered": ["Direct computation", "Step-by-step rules", "Transformation"],
             "chosen_path_reason": "Reframing reveals deeper structure and shorter path"},
            {"decision_point": "Selected reduction approach",
             "alternatives_considered": ["Expand and compute", "Transform and reduce"],
             "chosen_path_reason": "Reduction minimizes step count and reveals generality"},
        ]

    return {"level": level, "nodes": nodes, "edges": edges, "decisions": decisions}


# ---------------------------------------------------------------------------
# Node 3: Reasoning Graph Builder — enforces structure + validates constraints
# ---------------------------------------------------------------------------

def reasoning_graph_builder_node(state: ThinkingState) -> dict:
    """Enforce node + edge structure and validate against profile constraints.

    Rejects and regenerates if:
    - Profiles overlap (same strategies)
    - Beginner uses transformation
    - Expert has no transformation/reduction
    - Graphs are structurally similar

    Reads: reasoning_graphs, cognitive_profiles
    Writes: reasoning_graphs (refined), validation_passed, validation_notes
    """
    graphs = state["reasoning_graphs"]
    profiles = state["cognitive_profiles"]
    profile_map = {p["level"]: p for p in profiles}

    validation_notes = []
    validated_graphs = []

    for graph in graphs:
        level = graph["level"]
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        profile = profile_map.get(level, {})
        forbidden_ops = set(profile.get("forbidden_operations", []))
        max_abs = profile.get("max_abstraction", "LOW")
        abs_order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
        max_abs_val = abs_order.get(max_abs, 3)

        # Validate and fix nodes
        fixed_nodes = []
        for node in nodes:
            # Enforce forbidden operations
            if node.get("operation_type", "") in forbidden_ops:
                validation_notes.append(
                    f"{level}: replaced forbidden op '{node['operation_type']}'"
                )
                if level == "beginner":
                    node["operation_type"] = "compute"
                    node["strategy_type"] = "direct_application"
                else:
                    node["operation_type"] = "apply_rule"
                    node["strategy_type"] = "rule_based"

            # Enforce max abstraction
            node_abs = node.get("abstraction_level", "LOW")
            if abs_order.get(node_abs, 1) > max_abs_val:
                validation_notes.append(
                    f"{level}: capped abstraction from {node_abs} to {max_abs}"
                )
                node["abstraction_level"] = max_abs

            # Enforce valid strategy types
            if node.get("strategy_type", "") not in VALID_STRATEGY_TYPES:
                node["strategy_type"] = "direct_application"

            fixed_nodes.append(node)

        # Expert validation: must have at least one transformation or reduction
        if level == "expert":
            has_transform = any(
                n["operation_type"] in ("transform", "reframe", "abstract", "reduce")
                for n in fixed_nodes
            )
            if not has_transform:
                validation_notes.append(
                    "expert: no transformation/reduction found — added reframe step"
                )
                fixed_nodes.insert(0, {
                    "step_id": "e0_fix",
                    "operation_type": "reframe",
                    "concept_used": "problem reframing",
                    "input": state["problem"][:80],
                    "output": "Reframed problem representation",
                    "reasoning": "Expert must reframe before solving",
                    "abstraction_level": "HIGH",
                    "strategy_type": "transformation",
                })
                # Add edge from new node to first original node
                if fixed_nodes and len(fixed_nodes) > 1:
                    edges.insert(0, {
                        "from_step_id": "e0_fix",
                        "to_step_id": fixed_nodes[1]["step_id"],
                        "relation_type": "transforms",
                    })

        # Ensure edges exist between consecutive nodes
        node_ids = [n["step_id"] for n in fixed_nodes]
        edge_pairs = {(e["from_step_id"], e["to_step_id"]) for e in edges}
        for i in range(len(node_ids) - 1):
            if (node_ids[i], node_ids[i + 1]) not in edge_pairs:
                rel = "derives"
                next_op = fixed_nodes[i + 1].get("operation_type", "")
                if next_op in ("transform", "reframe", "abstract"):
                    rel = "transforms"
                elif next_op in ("reduce", "simplify"):
                    rel = "simplifies"
                edges.append({
                    "from_step_id": node_ids[i],
                    "to_step_id": node_ids[i + 1],
                    "relation_type": rel,
                })

        # Filter edges to only reference existing nodes
        node_id_set = set(node_ids)
        valid_edges = [
            e for e in edges
            if e["from_step_id"] in node_id_set and e["to_step_id"] in node_id_set
        ]

        validated_graphs.append({
            "level": level,
            "nodes": fixed_nodes,
            "edges": valid_edges,
            "decisions": graph.get("decisions", []),
        })

    # Cross-profile validation: check structural similarity
    if len(validated_graphs) >= 2:
        op_sets = []
        for g in validated_graphs:
            ops = tuple(sorted(n["operation_type"] for n in g["nodes"]))
            op_sets.append(ops)
        for i in range(len(op_sets)):
            for j in range(i + 1, len(op_sets)):
                if op_sets[i] == op_sets[j]:
                    validation_notes.append(
                        f"Warning: {validated_graphs[i]['level']} and "
                        f"{validated_graphs[j]['level']} have identical operation types"
                    )

    passed = len(validation_notes) == 0 or all(
        "Warning" in n or "replaced" in n or "capped" in n or "added" in n
        for n in validation_notes
    )

    return {
        "reasoning_graphs": validated_graphs,
        "validation_passed": passed,
        "validation_notes": validation_notes,
    }


# ---------------------------------------------------------------------------
# Node 4: Strategy-Constrained Generator — strategy_type per step
# ---------------------------------------------------------------------------

def strategy_constrained_generator_node(state: ThinkingState) -> dict:
    """Compute strategy distributions from the strategy_type on each node.

    Strategies are GENERATED during creation, not tagged post-hoc.
    This node computes the distribution metrics.

    Reads: reasoning_graphs
    Writes: strategy_distributions
    """
    graphs = state["reasoning_graphs"]
    distributions = []

    for graph in graphs:
        level = graph["level"]
        nodes = graph.get("nodes", [])
        total = max(len(nodes), 1)

        counts = {
            "direct_application": 0,
            "rule_based": 0,
            "transformation": 0,
            "reduction": 0,
            "optimization": 0,
        }
        strategies_used = set()

        for node in nodes:
            st = node.get("strategy_type", "direct_application")
            if st in counts:
                counts[st] += 1
                strategies_used.add(st)

        distributions.append({
            "level": level,
            "direct_application_pct": round(counts["direct_application"] / total * 100, 1),
            "rule_based_pct": round(counts["rule_based"] / total * 100, 1),
            "transformation_pct": round(counts["transformation"] / total * 100, 1),
            "reduction_pct": round(counts["reduction"] / total * 100, 1),
            "optimization_pct": round(counts["optimization"] / total * 100, 1),
            "strategies_used": sorted(list(strategies_used)),
        })

    return {"strategy_distributions": distributions}


# ---------------------------------------------------------------------------
# Node 5: Abstraction Analyzer — computes abstraction metrics
# ---------------------------------------------------------------------------

def abstraction_analyzer_node(state: ThinkingState) -> dict:
    """Compute explicit abstraction scoring for each reasoning graph.

    For each step: LOW (1) / MEDIUM (2) / HIGH (3).
    For each path: average, max, transitions.

    Reads: reasoning_graphs
    Writes: abstraction_data, reasoning_graphs (enriched with metrics)
    """
    graphs = state["reasoning_graphs"]
    abstraction_data = []
    enriched_graphs = []

    for graph in graphs:
        level = graph["level"]
        nodes = graph.get("nodes", [])

        abs_levels = [n.get("abstraction_level", "LOW") for n in nodes]
        abs_scores = [ABSTRACTION_SCORES.get(a, 1.0) for a in abs_levels]

        avg_abs = round(sum(abs_scores) / max(len(abs_scores), 1), 2)
        max_abs_val = max(abs_scores) if abs_scores else 1.0
        max_abs_label = "LOW"
        if max_abs_val >= 3.0:
            max_abs_label = "HIGH"
        elif max_abs_val >= 2.0:
            max_abs_label = "MEDIUM"

        # Compute transitions (where abstraction level changes)
        transitions = []
        for i in range(len(abs_levels) - 1):
            if abs_levels[i] != abs_levels[i + 1]:
                transitions.append(
                    f"{nodes[i]['step_id']}({abs_levels[i]}) → "
                    f"{nodes[i+1]['step_id']}({abs_levels[i+1]})"
                )

        metrics = {
            "average_abstraction": avg_abs,
            "max_abstraction": max_abs_label,
            "abstraction_transitions": transitions,
            "abstraction_flow": abs_levels,
        }
        abstraction_data.append({"level": level, "metrics": metrics})

        enriched = dict(graph)
        enriched["metadata"] = {
            **graph.get("metadata", {}),
            "abstraction_level": max_abs_label.lower(),
            "average_abstraction": avg_abs,
            "step_count": len(nodes),
            "edge_count": len(graph.get("edges", [])),
            "has_transformation": any(
                n.get("operation_type") in ("transform", "reframe", "abstract", "reduce")
                for n in nodes
            ),
        }
        enriched_graphs.append(enriched)

    return {"abstraction_data": abstraction_data, "reasoning_graphs": enriched_graphs}


# ---------------------------------------------------------------------------
# Node 6: Structural Comparator — graph shape + strategy + abstraction
# ---------------------------------------------------------------------------

def structural_comparator_node(state: ThinkingState) -> dict:
    """Compare reasoning graphs structurally — not descriptively.

    Compares:
    A. Graph Shape: node count, edge count, depth, branching, linear vs transformed
    B. Strategy Distribution: % of transformation/direct/etc per level
    C. Abstraction Flow: where abstraction increases, where simplification happens

    Reads: reasoning_graphs, strategy_distributions, abstraction_data
    Writes: comparison_results
    """
    graphs = state["reasoning_graphs"]
    strategy_dists = state["strategy_distributions"]
    abs_data = state["abstraction_data"]

    # A. Graph Shape
    graph_shape = {}
    for graph in graphs:
        level = graph["level"]
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        transform_ops = {"transform", "reframe", "abstract", "reduce", "optimize"}
        is_linear = not any(n["operation_type"] in transform_ops for n in nodes)
        graph_shape[level] = {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "depth": len(nodes),  # linear depth
            "is_linear": is_linear,
            "has_branching": len(edges) > len(nodes) - 1 if nodes else False,
        }

    # B. Strategy Distribution
    strategy_distribution = {}
    for sd in strategy_dists:
        strategy_distribution[sd["level"]] = {
            "direct_application_pct": sd.get("direct_application_pct", 0),
            "rule_based_pct": sd.get("rule_based_pct", 0),
            "transformation_pct": sd.get("transformation_pct", 0),
            "reduction_pct": sd.get("reduction_pct", 0),
            "optimization_pct": sd.get("optimization_pct", 0),
        }

    # C. Abstraction Flow
    abstraction_flow = {}
    for ad in abs_data:
        level = ad["level"]
        m = ad["metrics"]
        abstraction_flow[level] = {
            "average_abstraction": m.get("average_abstraction", 1.0),
            "max_abstraction": m.get("max_abstraction", "LOW"),
            "transitions": m.get("abstraction_transitions", []),
            "flow": m.get("abstraction_flow", []),
        }

    # Generate structural key differences
    key_differences = _compute_structural_differences(graph_shape, strategy_distribution, abstraction_flow)

    return {
        "comparison_results": {
            "graph_shape": graph_shape,
            "strategy_distribution": strategy_distribution,
            "abstraction_flow": abstraction_flow,
            "key_differences": key_differences,
        }
    }


def _compute_structural_differences(graph_shape: dict, strategy_dist: dict,
                                     abstraction_flow: dict) -> list[str]:
    """Derive key differences from structural data."""
    diffs = []

    # Node count differences
    beg = graph_shape.get("beginner", {})
    mid = graph_shape.get("intermediate", {})
    exp = graph_shape.get("expert", {})

    beg_nodes = beg.get("node_count", 0)
    mid_nodes = mid.get("node_count", 0)
    exp_nodes = exp.get("node_count", 0)

    if beg_nodes > 0 and exp_nodes > 0:
        diffs.append(
            f"Beginner uses {beg_nodes} nodes, intermediate uses {mid_nodes}, "
            f"expert uses {exp_nodes} nodes"
        )

    # Linear vs transformed
    if beg.get("is_linear") and not exp.get("is_linear", True):
        diffs.append(
            "Beginner follows a linear path; expert uses transformations"
        )

    # Strategy differences
    beg_strat = strategy_dist.get("beginner", {})
    exp_strat = strategy_dist.get("expert", {})
    if beg_strat.get("transformation_pct", 0) == 0 and exp_strat.get("transformation_pct", 0) > 0:
        diffs.append(
            f"Beginner has 0% transformation steps; expert has "
            f"{exp_strat['transformation_pct']}% transformation steps"
        )

    # Abstraction differences
    beg_abs = abstraction_flow.get("beginner", {})
    exp_abs = abstraction_flow.get("expert", {})
    beg_avg = beg_abs.get("average_abstraction", 1.0)
    exp_avg = exp_abs.get("average_abstraction", 1.0)
    if exp_avg > beg_avg:
        diffs.append(
            f"Average abstraction: beginner={beg_avg}, expert={exp_avg} "
            f"(expert operates at higher abstraction)"
        )

    # Abstraction transitions
    exp_trans = exp_abs.get("transitions", [])
    beg_trans = beg_abs.get("transitions", [])
    if len(exp_trans) > len(beg_trans):
        diffs.append(
            f"Expert has {len(exp_trans)} abstraction transitions; "
            f"beginner has {len(beg_trans)}"
        )

    return diffs


# ---------------------------------------------------------------------------
# Conditional edge: check if student answer exists
# ---------------------------------------------------------------------------

def _check_student_answer(state: ThinkingState) -> str:
    """Route to student_graph_converter if student_answer exists, else skip."""
    if state.get("student_answer", "").strip():
        return "has_student"
    return "no_student"


# ---------------------------------------------------------------------------
# Node 7: Student Graph Converter (CONDITIONAL)
# ---------------------------------------------------------------------------

def student_graph_converter_node(state: ThinkingState) -> dict:
    """Convert student answer to the SAME graph structure, then compare.

    Extracts steps, maps to operation_type / abstraction_level / strategy_type,
    and compares against all three cognitive levels.

    Reads: student_answer, reasoning_graphs, strategy_distributions, _llm_client
    Writes: student_graph
    """
    student_answer = state.get("student_answer", "")
    graphs = state["reasoning_graphs"]
    llm_client = state.get("_llm_client")

    student_graph = {
        "student_level_match": "unknown",
        "nodes": [],
        "edges": [],
        "abstraction_metrics": {
            "average_abstraction": 1.0,
            "max_abstraction": "LOW",
            "abstraction_transitions": [],
            "abstraction_flow": [],
        },
        "missing_nodes": [],
        "missing_transformations": [],
        "unnecessary_steps": [],
        "abstraction_mismatches": [],
        "strategy_distribution": {},
    }

    # Extract student reasoning into graph structure
    student_nodes = []
    if llm_client and student_answer:
        prompt = (
            "Convert this student's reasoning into a structured graph.\n\n"
            f"Student reasoning: {student_answer}\n\n"
            "Return a JSON object with:\n"
            '- "nodes": array of step objects, each with:\n'
            '  - "step_id": unique id (e.g. "s1")\n'
            '  - "operation_type": what the student did (identify, recall, compute, apply_rule, transform, etc.)\n'
            '  - "concept_used": concept or rule applied\n'
            '  - "input": what this step takes\n'
            '  - "output": what this step produces\n'
            '  - "reasoning": why this step was taken\n'
            '  - "abstraction_level": "LOW", "MEDIUM", or "HIGH"\n'
            '  - "strategy_type": "direct_application", "rule_based", "transformation", "reduction", or "optimization"\n'
            '- "edges": array of {from_step_id, to_step_id, relation_type}\n\n'
            "JSON object:"
        )
        result = _parse_json(_llm_call(llm_client, prompt, 1024), None)
        if isinstance(result, dict) and "nodes" in result:
            for s in result.get("nodes", []):
                abs_level = s.get("abstraction_level", "LOW").upper()
                if abs_level not in VALID_ABSTRACTION_LEVELS:
                    abs_level = "LOW"
                strategy = s.get("strategy_type", "direct_application")
                if strategy not in VALID_STRATEGY_TYPES:
                    strategy = "direct_application"
                student_nodes.append({
                    "step_id": s.get("step_id", str(uuid.uuid4())[:8]),
                    "operation_type": s.get("operation_type", "identify"),
                    "concept_used": s.get("concept_used", ""),
                    "input": s.get("input", ""),
                    "output": s.get("output", ""),
                    "reasoning": s.get("reasoning", ""),
                    "abstraction_level": abs_level,
                    "strategy_type": strategy,
                })

            student_edges = []
            snode_ids = {n["step_id"] for n in student_nodes}
            for e in result.get("edges", []):
                rel = e.get("relation_type", "derives")
                if rel not in VALID_RELATION_TYPES:
                    rel = "derives"
                if e.get("from_step_id") in snode_ids and e.get("to_step_id") in snode_ids:
                    student_edges.append({
                        "from_step_id": e["from_step_id"],
                        "to_step_id": e["to_step_id"],
                        "relation_type": rel,
                    })

            # Auto-generate edges if needed
            if len(student_edges) < len(student_nodes) - 1:
                student_edges = []
                for i in range(len(student_nodes) - 1):
                    student_edges.append({
                        "from_step_id": student_nodes[i]["step_id"],
                        "to_step_id": student_nodes[i + 1]["step_id"],
                        "relation_type": "derives",
                    })

            student_graph["nodes"] = student_nodes
            student_graph["edges"] = student_edges

    # Rule-based fallback for student graph extraction
    if not student_nodes and student_answer:
        sentences = [s.strip() for s in re.split(r'[.;]\s+', student_answer) if len(s.strip()) > 5]
        for i, sent in enumerate(sentences[:6]):
            student_lower = sent.lower()
            op = "compute"
            strategy = "direct_application"
            abs_level = "LOW"
            if any(kw in student_lower for kw in ["transform", "reframe", "convert"]):
                op = "transform"
                strategy = "transformation"
                abs_level = "HIGH"
            elif any(kw in student_lower for kw in ["simplif", "reduc"]):
                op = "reduce"
                strategy = "reduction"
                abs_level = "MEDIUM"
            elif any(kw in student_lower for kw in ["rule", "apply", "step", "decompos"]):
                op = "apply_rule"
                strategy = "rule_based"
                abs_level = "MEDIUM"
            elif any(kw in student_lower for kw in ["formula", "plug", "substitut"]):
                op = "substitute"
                strategy = "direct_application"
                abs_level = "LOW"
            student_nodes.append({
                "step_id": f"s{i+1}",
                "operation_type": op,
                "concept_used": sent[:50],
                "input": "",
                "output": "",
                "reasoning": sent,
                "abstraction_level": abs_level,
                "strategy_type": strategy,
            })

        student_edges_fb = []
        for i in range(len(student_nodes) - 1):
            student_edges_fb.append({
                "from_step_id": student_nodes[i]["step_id"],
                "to_step_id": student_nodes[i + 1]["step_id"],
                "relation_type": "derives",
            })

        student_graph["nodes"] = student_nodes
        student_graph["edges"] = student_edges_fb

    # Compute student abstraction metrics
    if student_nodes:
        abs_levels = [n.get("abstraction_level", "LOW") for n in student_nodes]
        abs_scores = [ABSTRACTION_SCORES.get(a, 1.0) for a in abs_levels]
        avg_abs = round(sum(abs_scores) / len(abs_scores), 2)
        max_abs_val = max(abs_scores)
        max_abs_label = "LOW"
        if max_abs_val >= 3.0:
            max_abs_label = "HIGH"
        elif max_abs_val >= 2.0:
            max_abs_label = "MEDIUM"

        transitions = []
        for i in range(len(abs_levels) - 1):
            if abs_levels[i] != abs_levels[i + 1]:
                transitions.append(f"{student_nodes[i]['step_id']}({abs_levels[i]}) → {student_nodes[i+1]['step_id']}({abs_levels[i+1]})")

        student_graph["abstraction_metrics"] = {
            "average_abstraction": avg_abs,
            "max_abstraction": max_abs_label,
            "abstraction_transitions": transitions,
            "abstraction_flow": abs_levels,
        }

        # Compute student strategy distribution
        total = max(len(student_nodes), 1)
        counts = {"direct_application": 0, "rule_based": 0, "transformation": 0, "reduction": 0, "optimization": 0}
        for n in student_nodes:
            st = n.get("strategy_type", "direct_application")
            if st in counts:
                counts[st] += 1
        student_graph["strategy_distribution"] = {
            k: round(v / total * 100, 1) for k, v in counts.items()
        }

    # Structural comparison against all levels
    student_ops = {n["operation_type"] for n in student_nodes}
    student_strategies = {n["strategy_type"] for n in student_nodes}

    # Find best level match
    best_match = "beginner"
    best_score = 0
    for graph in graphs:
        level = graph["level"]
        level_ops = {n["operation_type"] for n in graph.get("nodes", [])}
        overlap = len(student_ops & level_ops)
        if overlap > best_score:
            best_score = overlap
            best_match = level

    student_graph["student_level_match"] = best_match

    # Find missing nodes (ops that expert has but student doesn't)
    expert_graph = next((g for g in graphs if g["level"] == "expert"), None)
    if expert_graph:
        expert_ops = {n["operation_type"] for n in expert_graph.get("nodes", [])}
        missing = expert_ops - student_ops
        student_graph["missing_nodes"] = [
            f"Missing '{op}' step (used by expert)" for op in sorted(missing)
        ]

        # Missing transformations
        transform_ops = {"transform", "reframe", "abstract", "reduce"}
        missing_transforms = transform_ops & expert_ops - student_ops
        student_graph["missing_transformations"] = [
            f"No '{op}' transformation (expert uses this)" for op in sorted(missing_transforms)
        ]

    # Check for unnecessary steps
    if expert_graph:
        expert_node_count = len(expert_graph.get("nodes", []))
        student_node_count = len(student_nodes)
        if student_node_count > expert_node_count + 2:
            student_graph["unnecessary_steps"].append(
                f"Student uses {student_node_count} steps; expert solves in {expert_node_count}"
            )

    # Abstraction mismatches
    if expert_graph:
        expert_abs_data = next(
            (ad for ad in state.get("abstraction_data", []) if ad["level"] == "expert"),
            None
        )
        student_avg = student_graph["abstraction_metrics"].get("average_abstraction", 1.0)
        expert_avg = expert_abs_data["metrics"]["average_abstraction"] if expert_abs_data else 3.0
        if student_avg < expert_avg - 0.5:
            student_graph["abstraction_mismatches"].append(
                f"Student avg abstraction={student_avg} vs expert avg={expert_avg}"
            )

    return {"student_graph": student_graph}


# ---------------------------------------------------------------------------
# Node 8: Gap Generator — derives gaps from structure
# ---------------------------------------------------------------------------

def gap_generator_node(state: ThinkingState) -> dict:
    """Generate thinking gap insights derived from STRUCTURAL data, not text.

    Gap examples:
    - "Your reasoning contains 0 transformation steps; expert uses 2"
    - "Your abstraction level remains LOW throughout; expert shifts to HIGH at step 2"
    - "You use 5 steps; expert reduces problem to 2 steps"

    Reads: comparison_results, student_graph, reasoning_graphs, strategy_distributions,
           abstraction_data
    Writes: gap_analysis
    """
    comparison = state["comparison_results"]
    student = state.get("student_graph", {})
    graphs = state["reasoning_graphs"]
    abs_data = state.get("abstraction_data", [])
    student_answer = state.get("student_answer", "").strip()

    gaps = []

    # Always: structural differences between levels
    graph_shape = comparison.get("graph_shape", {})
    strategy_dist = comparison.get("strategy_distribution", {})
    abs_flow = comparison.get("abstraction_flow", {})

    for diff in comparison.get("key_differences", []):
        gaps.append({"insight": diff, "severity": "info", "source": "structural"})

    # Student-specific gaps
    if student_answer and student.get("nodes"):
        student_nodes = student.get("nodes", [])
        student_node_count = len(student_nodes)
        student_strategies = {n.get("strategy_type") for n in student_nodes}
        student_ops = {n.get("operation_type") for n in student_nodes}
        level_match = student.get("student_level_match", "unknown")

        # Level match insight
        if level_match != "unknown":
            level_descriptions = {
                "beginner": "direct application",
                "intermediate": "rule-based application",
                "expert": "transformation-based reasoning",
            }
            level_desc = level_descriptions.get(level_match, level_match)
            gaps.append({
                "insight": f"Your approach follows {level_match}-level reasoning: {level_desc}",
                "severity": "info" if level_match == "expert" else "warning",
                "source": "comparison",
            })

        # Step count comparison
        expert_shape = graph_shape.get("expert", {})
        expert_node_count = expert_shape.get("node_count", 0)
        if expert_node_count > 0 and student_node_count > expert_node_count:
            gaps.append({
                "insight": (
                    f"You use {student_node_count} steps; "
                    f"expert reduces problem to {expert_node_count} steps"
                ),
                "severity": "warning",
                "source": "structural",
            })

        # Transformation gap
        student_transform_count = sum(
            1 for n in student_nodes
            if n.get("strategy_type") in ("transformation", "reduction")
        )
        expert_transform_pct = strategy_dist.get("expert", {}).get("transformation_pct", 0)
        expert_reduction_pct = strategy_dist.get("expert", {}).get("reduction_pct", 0)
        expert_graph = next((g for g in graphs if g["level"] == "expert"), None)
        expert_transform_count = 0
        if expert_graph:
            expert_transform_count = sum(
                1 for n in expert_graph.get("nodes", [])
                if n.get("strategy_type") in ("transformation", "reduction")
            )
        if student_transform_count < expert_transform_count:
            gaps.append({
                "insight": (
                    f"Your reasoning contains {student_transform_count} transformation steps; "
                    f"expert uses {expert_transform_count}"
                ),
                "severity": "warning",
                "source": "strategy",
            })

        # Abstraction level gap
        student_abs = student.get("abstraction_metrics", {})
        student_avg_abs = student_abs.get("average_abstraction", 1.0)
        student_max_abs = student_abs.get("max_abstraction", "LOW")
        student_abs_flow = student_abs.get("abstraction_flow", [])

        expert_abs = abs_flow.get("expert", {})
        expert_avg_abs = expert_abs.get("average_abstraction", 1.0)
        expert_max_abs = expert_abs.get("max_abstraction", "LOW")

        if student_max_abs == "LOW" and expert_max_abs == "HIGH":
            gaps.append({
                "insight": (
                    "Your abstraction level remains LOW throughout; "
                    f"expert shifts to HIGH"
                ),
                "severity": "critical",
                "source": "abstraction",
            })
        elif student_avg_abs < expert_avg_abs - 0.5:
            gaps.append({
                "insight": (
                    f"Your average abstraction ({student_avg_abs}) is significantly lower "
                    f"than expert ({expert_avg_abs})"
                ),
                "severity": "warning",
                "source": "abstraction",
            })

        # Missing strategies
        expert_strategies = set()
        if expert_graph:
            expert_strategies = {n.get("strategy_type") for n in expert_graph.get("nodes", [])}
        missing = expert_strategies - student_strategies
        for ms in sorted(missing):
            gaps.append({
                "insight": f"You follow {', '.join(sorted(student_strategies))} only; missing {ms.replace('_', ' ')} strategy",
                "severity": "warning",
                "source": "strategy",
            })

        # Missing nodes
        for mn in student.get("missing_nodes", []):
            gaps.append({
                "insight": mn,
                "severity": "warning",
                "source": "structural",
            })

        # Abstraction mismatches
        for am in student.get("abstraction_mismatches", []):
            gaps.append({
                "insight": am,
                "severity": "critical",
                "source": "abstraction",
            })

    else:
        # No student answer — generate level comparison gaps
        beg_shape = graph_shape.get("beginner", {})
        exp_shape = graph_shape.get("expert", {})
        beg_nodes = beg_shape.get("node_count", 0)
        exp_nodes = exp_shape.get("node_count", 0)

        if beg_nodes > 0 and exp_nodes > 0:
            gaps.append({
                "insight": (
                    f"Beginner uses {beg_nodes} steps; expert uses {exp_nodes} steps"
                ),
                "severity": "info",
                "source": "structural",
            })

        # Strategy comparison
        beg_strat = strategy_dist.get("beginner", {})
        exp_strat = strategy_dist.get("expert", {})
        if beg_strat.get("transformation_pct", 0) == 0 and exp_strat.get("transformation_pct", 0) > 0:
            gaps.append({
                "insight": (
                    f"Beginner has 0% transformation; expert has "
                    f"{exp_strat['transformation_pct']}% transformation steps"
                ),
                "severity": "info",
                "source": "strategy",
            })

        # Abstraction comparison
        beg_abs = abs_flow.get("beginner", {})
        exp_abs = abs_flow.get("expert", {})
        if beg_abs.get("max_abstraction") == "LOW" and exp_abs.get("max_abstraction") == "HIGH":
            gaps.append({
                "insight": "Beginner stays at LOW abstraction; expert reaches HIGH",
                "severity": "info",
                "source": "abstraction",
            })

    return {"gap_analysis": gaps}


# ---------------------------------------------------------------------------
# Graph Construction — builds the LangGraph StateGraph (8 nodes)
# ---------------------------------------------------------------------------

def build_thinking_simulation_graph():
    """Build and compile the Thinking Simulation LangGraph StateGraph.

    Returns a compiled graph with execution flow:
        START → cognitive_profile_generator → parallel_reasoning_generator
        → reasoning_graph_builder → strategy_constrained_generator
        → abstraction_analyzer → structural_comparator
        → (if student exists) student_graph_converter → gap_generator → END

    8 nodes, all pure functions, no classes, no wrappers.
    """
    graph = StateGraph(ThinkingState)

    # Register pure-function nodes
    graph.add_node("cognitive_profile_generator", cognitive_profile_generator_node)
    graph.add_node("parallel_reasoning_generator", parallel_reasoning_generator_node)
    graph.add_node("reasoning_graph_builder", reasoning_graph_builder_node)
    graph.add_node("strategy_constrained_generator", strategy_constrained_generator_node)
    graph.add_node("abstraction_analyzer", abstraction_analyzer_node)
    graph.add_node("structural_comparator", structural_comparator_node)
    graph.add_node("student_graph_converter", student_graph_converter_node)
    graph.add_node("gap_generator", gap_generator_node)

    # Strict sequential edges (NON-NEGOTIABLE order)
    graph.add_edge(START, "cognitive_profile_generator")
    graph.add_edge("cognitive_profile_generator", "parallel_reasoning_generator")
    graph.add_edge("parallel_reasoning_generator", "reasoning_graph_builder")
    graph.add_edge("reasoning_graph_builder", "strategy_constrained_generator")
    graph.add_edge("strategy_constrained_generator", "abstraction_analyzer")
    graph.add_edge("abstraction_analyzer", "structural_comparator")

    # Conditional edge: student graph converter only if student_answer exists
    graph.add_conditional_edges(
        "structural_comparator",
        _check_student_answer,
        {"has_student": "student_graph_converter", "no_student": "gap_generator"},
    )
    graph.add_edge("student_graph_converter", "gap_generator")
    graph.add_edge("gap_generator", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Public API — used by the backend to execute the thinking simulation
# ---------------------------------------------------------------------------

class ThinkingSimulationEngine:
    """Entry point that holds runtime dependencies and invokes the graph.

    This is NOT an agent class. It only:
    1. Stores reference to llm_client
    2. Injects it into shared state
    3. Calls graph.invoke()

    All reasoning logic lives in the graph nodes above.
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.graph = build_thinking_simulation_graph()

    def simulate(self, problem: str, student_answer: str = "") -> dict:
        """Execute the thinking simulation pipeline.

        Args:
            problem: The problem or question to simulate reasoning for.
            student_answer: Optional student answer to compare against.

        Returns:
            Dict with reasoning graphs, strategy distributions, structural
            comparison, student graph, and gap analysis.

        Raises:
            ValueError: If problem is empty.
        """
        if not problem or not problem.strip():
            raise ValueError("Problem text is empty.")

        initial_state: ThinkingState = {
            "_llm_client": self.llm_client,
            "problem": problem.strip(),
            "student_answer": student_answer.strip() if student_answer else "",
            "cognitive_profiles": [],
            "reasoning_graphs": [],
            "strategy_distributions": [],
            "abstraction_data": [],
            "comparison_results": {},
            "student_graph": {},
            "gap_analysis": [],
            "validation_passed": True,
            "validation_notes": [],
        }

        final_state = self.graph.invoke(initial_state)

        return {
            "cognitive_profiles": final_state.get("cognitive_profiles", []),
            "reasoning_paths": final_state.get("reasoning_graphs", []),
            "strategy_tags": final_state.get("strategy_distributions", []),
            "comparison_results": final_state.get("comparison_results", {}),
            "student_comparison": final_state.get("student_graph", {}),
            "gap_analysis": final_state.get("gap_analysis", []),
            "validation_passed": final_state.get("validation_passed", True),
            "validation_notes": final_state.get("validation_notes", []),
        }
