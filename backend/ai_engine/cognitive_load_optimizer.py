"""Cognitive Load Optimizer -- LangGraph-based real-time reasoning flow regulator.

This system sits between reasoning output and the user. It does NOT change
the correctness of explanations -- it controls HOW they are presented.

Architecture (LangGraph cyclic StateGraph, 6 nodes):
    START -> explanation_analyzer -> user_state_tracker -> load_estimator
    -> control_engine -> granularity_controller
    -> feedback_manager -> (conditional: loop back or END)

All nodes are pure functions operating on shared CognitiveLoadState.
The graph is cyclic -- the feedback manager decides whether to
re-optimize or finalize.
"""

import re
from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from ..schemas import (
    ExplanationStep,
    UserCognitiveState,
    CognitiveLoadMetrics,
    ControlAction,
)


# ---------------------------------------------------------------------------
# Shared State
# ---------------------------------------------------------------------------

class CognitiveLoadState(TypedDict):
    """Shared state for the Cognitive Load Optimizer graph."""

    # Input
    raw_explanation: str
    user_id: str

    # Explanation analysis (written by explanation_analyzer)
    steps: list[dict]           # list of ExplanationStep dicts

    # User state (written by user_state_tracker)
    user_state: dict            # UserCognitiveState dict

    # Load metrics (written by load_estimator)
    load_metrics: dict          # CognitiveLoadMetrics dict

    # Control decisions (written by control_engine)
    load_state: str             # overload / optimal / underload
    reasoning_mode: str         # fine-grained / medium / coarse
    control_actions: list[dict] # list of ControlAction dicts

    # Restructured output (written by granularity_controller)
    adapted_steps: list[dict]   # list of ExplanationStep dicts

    # Feedback loop (written by feedback_manager)
    iteration: int
    max_iterations: int
    converged: bool


# ---------------------------------------------------------------------------
# In-memory user state store (persistent across requests within process)
# ---------------------------------------------------------------------------

_user_states: dict[str, dict] = {}


def _get_user_state(user_id: str) -> dict:
    """Retrieve or initialize user cognitive state."""
    if user_id not in _user_states:
        state = UserCognitiveState(user_id=user_id)
        _user_states[user_id] = state.model_dump()
    return _user_states[user_id].copy()


def _save_user_state(user_id: str, state: dict) -> None:
    """Persist updated user state."""
    _user_states[user_id] = state.copy()


# ---------------------------------------------------------------------------
# Node 1: Explanation Analyzer (lightweight -- NO LLM)
# ---------------------------------------------------------------------------

def explanation_analyzer_node(state: CognitiveLoadState) -> dict:
    """Break explanation into steps using lightweight sentence splitting.

    This is a deterministic, rule-based analyzer -- NO LLM.
    The optimizer is a controller, not an analyzer.

    Reads: raw_explanation
    Writes: steps
    """
    raw = state["raw_explanation"]
    steps = []

    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', raw.strip())
    for i, sent in enumerate(sentences):
        sent = sent.strip()
        if len(sent) < 5:
            continue

        # Heuristic abstraction: longer sentences = more abstract
        word_count = len(sent.split())
        if word_count > 30:
            abs_level = "abstract"
        elif word_count > 15:
            abs_level = "semi-abstract"
        else:
            abs_level = "concrete"

        # Extract concept tokens (capitalized words > 2 chars)
        concepts = []
        for word in sent.split():
            cleaned = re.sub(r'[^a-zA-Z]', '', word)
            if cleaned and cleaned[0].isupper() and len(cleaned) > 2:
                concepts.append(cleaned)

        step = ExplanationStep(
            step_id=f"s{len(steps)+1}",
            content=sent,
            concepts=concepts,
            abstraction_level=abs_level,
            depends_on=[f"s{len(steps)}"] if steps else [],
        )
        steps.append(step.model_dump())

    return {"steps": steps}


# ---------------------------------------------------------------------------
# Node 2: User State Tracker
# ---------------------------------------------------------------------------

def user_state_tracker_node(state: CognitiveLoadState) -> dict:
    """Load and return the current user cognitive state.

    Reads: user_id
    Writes: user_state
    """
    user_id = state.get("user_id", "default")
    user_state = _get_user_state(user_id)
    return {"user_state": user_state}


# ---------------------------------------------------------------------------
# Node 3: Load Estimator
# ---------------------------------------------------------------------------

def load_estimator_node(state: CognitiveLoadState) -> dict:
    """Compute cognitive load from explanation structure.

    Three dimensions:
    - step_density: steps per 100 words of content
    - concept_gap: average new concepts introduced per step transition
    - memory_demand: max concurrent dependencies + concepts any step holds

    On loop iterations, uses adapted_steps instead of original steps.

    Reads: steps (or adapted_steps on loop iterations)
    Writes: load_metrics
    """
    # On loop iterations, use adapted_steps; on first pass, use steps
    iteration = state.get("iteration", 0)
    if iteration > 0 and state.get("adapted_steps"):
        steps = state["adapted_steps"]
    else:
        steps = state.get("steps", [])

    if not steps:
        return {"load_metrics": CognitiveLoadMetrics().model_dump()}

    # Step density: steps per 100 words
    total_words = sum(len(s.get("content", "").split()) for s in steps)
    step_density = (len(steps) / max(total_words, 1)) * 100

    # Concept gap: average new concepts between consecutive steps
    total_new = 0
    for i in range(1, len(steps)):
        prev = set(steps[i - 1].get("concepts", []))
        curr = set(steps[i].get("concepts", []))
        total_new += len(curr - prev)
    concept_gap = total_new / max(len(steps) - 1, 1) if len(steps) > 1 else 0

    # Memory demand: max dependencies + concepts any single step holds
    memory_demand = 0.0
    for s in steps:
        load = len(s.get("depends_on", [])) + len(s.get("concepts", []))
        memory_demand = max(memory_demand, float(load))

    # Composite load (0-10 scale)
    total_load = min(
        (step_density * 2.0) + (concept_gap * 2.5) + (memory_demand * 1.5),
        10.0,
    )

    metrics = CognitiveLoadMetrics(
        step_density=round(step_density, 2),
        concept_gap=round(concept_gap, 2),
        memory_demand=round(memory_demand, 2),
        total_load=round(total_load, 2),
    )
    return {"load_metrics": metrics.model_dump()}


# ---------------------------------------------------------------------------
# Node 4: Control Engine
# ---------------------------------------------------------------------------

def control_engine_node(state: CognitiveLoadState) -> dict:
    """Compare load vs user capacity and decide adaptation strategy.

    User capacity = (understanding x 5) + (stability x 5) on 0-10 scale.
    Deterministic decisions only.

    Reads: load_metrics, user_state, steps (or adapted_steps)
    Writes: load_state, reasoning_mode, control_actions
    """
    load_metrics = state.get("load_metrics", {})
    user_state = state.get("user_state", {})

    total_load = load_metrics.get("total_load", 5.0)
    understanding = user_state.get("understanding_level", 0.5)
    stability = user_state.get("reasoning_stability", 0.5)

    user_capacity = (understanding * 5.0) + (stability * 5.0)

    control_actions = []

    if total_load > user_capacity + 1.5:
        # --- OVERLOAD ---
        load_state = "overload"
        reasoning_mode = "fine-grained"

        control_actions.append(ControlAction(
            action="split_steps",
            reason=f"Reducing complexity: splitting steps (load={total_load:.1f} > capacity={user_capacity:.1f})",
        ).model_dump())

        # Find which steps are overloaded
        iteration = state.get("iteration", 0)
        steps = state["adapted_steps"] if iteration > 0 and state.get("adapted_steps") else state.get("steps", [])
        for s in steps:
            word_count = len(s.get("content", "").split())
            if word_count > 25:
                sid = s.get("step_id", "?")
                control_actions.append(ControlAction(
                    action="overload_at_step",
                    reason=f"Overload detected at step {sid} ({word_count} words)",
                ).model_dump())

        if load_metrics.get("concept_gap", 0) > 2.0:
            control_actions.append(ControlAction(
                action="add_intermediate",
                reason="Adding intermediate reasoning to bridge concept gaps",
            ).model_dump())

        if load_metrics.get("memory_demand", 0) > 4.0:
            control_actions.append(ControlAction(
                action="reduce_abstraction",
                reason="Reducing abstraction to lower memory demand",
            ).model_dump())

    elif total_load < user_capacity - 2.0:
        # --- UNDERLOAD ---
        load_state = "underload"
        reasoning_mode = "coarse"

        control_actions.append(ControlAction(
            action="merge_steps",
            reason=f"Increasing abstraction: skipping basics (load={total_load:.1f} < capacity={user_capacity:.1f})",
        ).model_dump())

        if load_metrics.get("step_density", 0) > 3.0:
            control_actions.append(ControlAction(
                action="increase_abstraction",
                reason="Compressing reasoning: raising abstraction level",
            ).model_dump())

    else:
        # --- OPTIMAL ---
        load_state = "optimal"
        reasoning_mode = "medium"

        if total_load > user_capacity:
            control_actions.append(ControlAction(
                action="add_checkpoints",
                reason="Borderline load: adding checkpoints for safety",
            ).model_dump())
        else:
            control_actions.append(ControlAction(
                action="maintain",
                reason="Load matches capacity -- maintaining current structure",
            ).model_dump())

    return {
        "load_state": load_state,
        "reasoning_mode": reasoning_mode,
        "control_actions": control_actions,
    }


# ---------------------------------------------------------------------------
# Node 5: Granularity Controller (includes restructuring)
# ---------------------------------------------------------------------------

def granularity_controller_node(state: CognitiveLoadState) -> dict:
    """Adjust step size and abstraction based on control decisions.

    Active abstraction control:
      overload  -> split large steps, force concrete abstraction
      underload -> merge short steps, raise abstraction level
      optimal   -> keep as-is, possibly add checkpoints

    Also cleans dependency references for consistency.

    Reads: steps (or adapted_steps on loop), load_state, control_actions
    Writes: adapted_steps
    """
    iteration = state.get("iteration", 0)
    if iteration > 0 and state.get("adapted_steps"):
        steps = state["adapted_steps"]
    else:
        steps = state.get("steps", [])

    load_state = state.get("load_state", "optimal")
    actions = state.get("control_actions", [])
    action_types = {a.get("action", "") for a in actions}

    if not steps:
        return {"adapted_steps": []}

    adapted = []

    if load_state == "overload":
        for s in steps:
            content = s.get("content", "")
            words = content.split()

            if len(words) > 25 and "split_steps" in action_types:
                # Split into two sub-steps at nearest sentence boundary
                mid = len(words) // 2
                split_idx = mid
                for j in range(mid, min(mid + 10, len(words))):
                    if j > 0 and words[j - 1].endswith(('.', '!', '?', ',', ';')):
                        split_idx = j
                        break

                part1 = " ".join(words[:split_idx])
                part2 = " ".join(words[split_idx:])
                concepts = s.get("concepts", [])
                sid = s["step_id"]

                adapted.append(ExplanationStep(
                    step_id=f"{sid}a",
                    content=part1,
                    concepts=concepts[: len(concepts) // 2 + 1],
                    abstraction_level="concrete",
                    depends_on=s.get("depends_on", []),
                ).model_dump())
                adapted.append(ExplanationStep(
                    step_id=f"{sid}b",
                    content=part2,
                    concepts=concepts[len(concepts) // 2 + 1 :],
                    abstraction_level="concrete",
                    depends_on=[f"{sid}a"],
                ).model_dump())
            else:
                # Force abstraction down toward concrete
                abs_level = s.get("abstraction_level", "concrete")
                if abs_level != "concrete":
                    abs_map = {"abstract": "semi-abstract", "semi-abstract": "concrete"}
                    abs_level = abs_map.get(abs_level, abs_level)
                adapted.append(ExplanationStep(
                    step_id=s["step_id"],
                    content=content,
                    concepts=s.get("concepts", []),
                    abstraction_level=abs_level,
                    depends_on=s.get("depends_on", []),
                ).model_dump())

    elif load_state == "underload":
        abs_up = {"concrete": "semi-abstract", "semi-abstract": "abstract"}
        i = 0
        while i < len(steps):
            if (
                i + 1 < len(steps)
                and "merge_steps" in action_types
                and len(steps[i].get("content", "").split()) < 15
                and len(steps[i + 1].get("content", "").split()) < 15
            ):
                merged_content = (
                    steps[i].get("content", "") + " "
                    + steps[i + 1].get("content", "")
                )
                merged_concepts = list(set(
                    steps[i].get("concepts", [])
                    + steps[i + 1].get("concepts", [])
                ))
                base_abs = steps[i].get("abstraction_level", "concrete")
                new_abs = abs_up.get(base_abs, base_abs)

                adapted.append(ExplanationStep(
                    step_id=steps[i]["step_id"],
                    content=merged_content.strip(),
                    concepts=merged_concepts,
                    abstraction_level=new_abs,
                    depends_on=steps[i].get("depends_on", []),
                ).model_dump())
                i += 2
            else:
                s = steps[i]
                abs_level = s.get("abstraction_level", "concrete")
                if "increase_abstraction" in action_types:
                    abs_level = abs_up.get(abs_level, abs_level)
                adapted.append(ExplanationStep(
                    step_id=s["step_id"],
                    content=s.get("content", ""),
                    concepts=s.get("concepts", []),
                    abstraction_level=abs_level,
                    depends_on=s.get("depends_on", []),
                ).model_dump())
                i += 1

    else:
        # Optimal -- keep structure, optionally add checkpoints
        for i, s in enumerate(steps):
            adapted.append(ExplanationStep(
                step_id=s["step_id"],
                content=s.get("content", ""),
                concepts=s.get("concepts", []),
                abstraction_level=s.get("abstraction_level", "concrete"),
                depends_on=s.get("depends_on", []),
            ).model_dump())
            if (
                "add_checkpoints" in action_types
                and (i + 1) % 3 == 0
                and i + 1 < len(steps)
            ):
                adapted.append(ExplanationStep(
                    step_id=f"checkpoint_{i + 1}",
                    content="[Checkpoint: Verify understanding of steps up to this point]",
                    concepts=[],
                    abstraction_level="concrete",
                    depends_on=[s["step_id"]],
                ).model_dump())

    # Clean dependency references
    valid_ids = {s.get("step_id", "") for s in adapted}
    for s in adapted:
        s["depends_on"] = [d for d in s.get("depends_on", []) if d in valid_ids]

    return {"adapted_steps": adapted}


# ---------------------------------------------------------------------------
# Node 6: Feedback Manager
# ---------------------------------------------------------------------------

def feedback_manager_node(state: CognitiveLoadState) -> dict:
    """Update user state and determine whether to loop.

    After adaptation:
    1. Update user state based on load outcome
    2. Decide if another iteration is needed
    3. Save user state for future interactions

    Reads: user_state, load_state, iteration, max_iterations
    Writes: user_state, iteration, converged
    """
    user_state = state.get("user_state", {})
    load_state = state.get("load_state", "optimal")
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)

    interaction_count = user_state.get("interaction_count", 0) + 1
    understanding = user_state.get("understanding_level", 0.5)
    stability = user_state.get("reasoning_stability", 0.5)
    learning_speed = user_state.get("learning_speed", 0.5)
    overload_signals = user_state.get("overload_signals", 0)

    if load_state == "overload":
        understanding = max(0.0, understanding - 0.05)
        stability = max(0.0, stability - 0.05)
        overload_signals += 1
    elif load_state == "underload":
        understanding = min(1.0, understanding + 0.05)
        stability = min(1.0, stability + 0.03)
        overload_signals = max(0, overload_signals - 1)
    else:
        stability = min(1.0, stability + 0.02)
        learning_speed = min(1.0, learning_speed + 0.02)

    updated = UserCognitiveState(
        user_id=user_state.get("user_id", "default"),
        understanding_level=round(understanding, 3),
        reasoning_stability=round(stability, 3),
        learning_speed=round(learning_speed, 3),
        overload_signals=overload_signals,
        interaction_count=interaction_count,
    )
    updated_dict = updated.model_dump()

    _save_user_state(updated_dict["user_id"], updated_dict)

    new_iteration = iteration + 1
    converged = (load_state == "optimal") or (new_iteration >= max_iterations)

    return {
        "user_state": updated_dict,
        "iteration": new_iteration,
        "converged": converged,
    }


# ---------------------------------------------------------------------------
# Conditional edge: loop or end
# ---------------------------------------------------------------------------

def _should_loop(state: CognitiveLoadState) -> str:
    """Decide whether to re-optimize or finalize."""
    if state.get("converged", True):
        return "end"
    return "loop"


# ---------------------------------------------------------------------------
# Graph Construction
# ---------------------------------------------------------------------------

def build_cognitive_load_graph():
    """Build and compile the LangGraph StateGraph (6 nodes, cyclic).

    START -> explanation_analyzer -> user_state_tracker -> load_estimator
    -> control_engine -> granularity_controller
    -> feedback_manager -> (loop back to load_estimator OR END)
    """
    graph = StateGraph(CognitiveLoadState)

    graph.add_node("explanation_analyzer", explanation_analyzer_node)
    graph.add_node("user_state_tracker", user_state_tracker_node)
    graph.add_node("load_estimator", load_estimator_node)
    graph.add_node("control_engine", control_engine_node)
    graph.add_node("granularity_controller", granularity_controller_node)
    graph.add_node("feedback_manager", feedback_manager_node)

    graph.add_edge(START, "explanation_analyzer")
    graph.add_edge("explanation_analyzer", "user_state_tracker")
    graph.add_edge("user_state_tracker", "load_estimator")
    graph.add_edge("load_estimator", "control_engine")
    graph.add_edge("control_engine", "granularity_controller")
    graph.add_edge("granularity_controller", "feedback_manager")

    # Cyclic feedback: loop back to load_estimator or end
    graph.add_conditional_edges(
        "feedback_manager",
        _should_loop,
        {"loop": "load_estimator", "end": END},
    )

    return graph.compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class CognitiveLoadOptimizer:
    """Entry point for cognitive load optimization.

    Holds the compiled LangGraph and invokes it.
    All logic lives in the graph nodes above.
    """

    def __init__(self, llm_client=None):
        # LLM client accepted for interface compatibility but NOT used.
        # The optimizer is deterministic -- no LLM dependency.
        self.graph = build_cognitive_load_graph()

    def optimize(self, explanation: str, user_id: str = "default") -> dict:
        """Optimize an explanation for cognitive load.

        Args:
            explanation: Raw explanation text.
            user_id: User identifier for state tracking.

        Returns:
            Dict with adapted_explanation, load_state, control_actions,
            user_state, load_metrics, reasoning_mode.
        """
        if not explanation or not explanation.strip():
            raise ValueError("Explanation text is empty.")

        initial_state: CognitiveLoadState = {
            "raw_explanation": explanation,
            "user_id": user_id,
            "steps": [],
            "user_state": {},
            "load_metrics": {},
            "load_state": "optimal",
            "reasoning_mode": "medium",
            "control_actions": [],
            "adapted_steps": [],
            "iteration": 0,
            "max_iterations": 3,
            "converged": False,
        }

        final_state = self.graph.invoke(initial_state)

        return {
            "adapted_explanation": final_state.get("adapted_steps", []),
            "load_state": final_state.get("load_state", "optimal"),
            "control_actions": final_state.get("control_actions", []),
            "user_state": final_state.get("user_state", {}),
            "load_metrics": final_state.get("load_metrics", {}),
            "reasoning_mode": final_state.get("reasoning_mode", "medium"),
        }
