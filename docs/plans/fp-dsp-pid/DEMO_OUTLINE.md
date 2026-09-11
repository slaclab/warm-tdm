# ECC AI Seminar Demo — Use Case 2: AI-Assisted Feature Addition

**Presenter:** Ben Reese  
**Time:** ~5 minutes  
**Tool:** Claude Code (Anthropic CLI agent)

**Audience note:** Familiar with FPGAs, Python, VHDL, PID loops, fixed vs
floating point — but NOT familiar with this specific project. Show that the
agent handled complex domain-specific design decisions, but don't get lost
in the details. Focus on the *process* and the *interaction pattern*.

---

## Slide 1: Title

**AI-Assisted Feature Addition To Existing Code**  
Generative AI Use Case 2  
Ben Reese

---

## Slide 2: The Task

**Converting a Fixed-Point PID Controller to Floating Point**

- FPGA-based detector readout system (VHDL + Python control software)
- PID servo module: ~1000 lines of VHDL, 8 parallel instances
- Goal: replace fixed-point math with IEEE 754 float32
  - Better dynamic range, simpler coefficient tuning from software
  - Reuse Xilinx floating-point IP cores already in the design

**Why this is a good AI-assisted task:**
- Not greenfield — must integrate into a large existing codebase
- Crosses firmware (VHDL) and software (Python) boundaries
- Requires understanding the existing design before writing new code
- Many files touched, but the *design work* is the hard part

---

## Slide 3: The Workflow

**Claude Code operates in the terminal alongside your normal dev tools**

```
  You type                    Agent does
  ─────────────────────────── ────────────────────────────────────
  "Make a plan for FP PID"  → Reads codebase, proposes architecture
  "New module, not in-place" → Updates plan, asks follow-up questions
  "Yes, go ahead"            → Writes ~800 lines across 15 files
  "Missing the FluxQuantum   → Fixes it, matches existing pattern
   LinkVariable pattern"
```

Typical session: ~30 minutes of interaction for a feature that would take
a day or more by hand.

---

## Slide 4: AGENTS.md — Giving the Agent Context

**The single most impactful thing you can add to a repo for AI assistance.**

A Markdown file at the repo root that describes:
- Architecture and data flow
- Where to find things (file/directory map)
- Naming conventions and coding patterns
- How to start for each task area

**Snippets from this project's AGENTS.md:**

```
### Data Flow (Column Board)

ADC → DataPath → AdcDsp (PID + flux-jump) → EventBuilder → Host
                     ↕
               FastDacDriver (feedback DAC)
```

```
| Task Area       | Start With These Files                         |
|-----------------|-------------------------------------------------|
| DSP / data path | DataPath.vhd, AdcDsp.vhd, BiquadFilter.vhd     |
```

```
## Firmware Conventions
- Generics suffixed `_G` (e.g., TPD_G, SIMULATION_G)
- Constants suffixed `_C`
- Architecture always named `rtl`
```

**Without AGENTS.md:** agent spends many turns guessing file locations.  
**With AGENTS.md:** agent navigates the codebase immediately and follows
the right conventions from the start.

---

## Slide 5: AGENTS.md → Plan Docs

**AGENTS.md also directs how work is tracked:**

```
For substantial feature work, keep planning, progress, and handoff
Markdown under docs/plans/<task-name>/.
```

The agent automatically created `docs/plans/fp-dsp-pid/PLAN.md` — no extra
prompting needed. Snippet from the generated plan:

```markdown
# Floating-Point PID (AdcDspFp)

## Scope
New module, port-compatible with AdcDsp, selectable via generic.

## Architecture
| Core     | Operation   | Latency  |
|----------|-------------|----------|
| FpMac    | A*B+C       | 4 cycles |
| Int2Fp   | int → float | 2 cycles |
| Fp2Int   | float → int | 2 cycles |

## Key Design Decisions
1. Track unwrapped feedback value as primary state
2. Pass float directly to downstream filter (skip redundant conversion)
3. Iterative flux jump loop (handles multi-quantum jumps)
```

**Why this matters:**
- Plans survive context window resets (agent resumes in new sessions)
- Engineers can review the approach before code is written
- Decisions are captured with rationale, not buried in chat logs

**Note:** This example fit in one session. Most features won't — they span
multiple sessions, days, or handoffs between people. Plan docs become
essential for continuity. Good practice to track regardless of scope.

---

## Slide 6: Plan → Iteration

**The plan evolved through back-and-forth dialogue:**

| I asked | Agent responded |
|---------|-----------------|
| "New module or modify in place?" | Proposed new file, generic to select |
| "Can we pass float directly to the next filter stage?" | Yes — added a bypass generic, eliminates 8 redundant conversions |
| "How does anti-windup work now?" | Sign-bit comparison, no extra FP operation needed |
| "Support multi-quantum flux jumps?" | Added iterative loop, widened counter from 9 to 16 bits |

**Key point:** The agent doesn't just execute — it participates in the design
conversation. But the *engineer* makes the architectural calls.

---

## Slide 7: Implementation Output

**Files created/modified in one session:**

| Action | Files | What |
|--------|-------|------|
| Created | `AdcDspFp.vhd` | 600-line FP PID module |
| Created | `Fp2Int.xci` | Xilinx IP core (float→int) |
| Created | `_AdcDspFp.py` | Python register driver |
| Modified | `DataPath.vhd` | Conditional instantiation |
| Modified | `BiquadFilter.vhd` | Float input bypass |
| Modified | 10+ other files | Build system, CLI flag, SW stack |

**~800 lines of production code** across VHDL, Python, TCL, and IP
configuration — all consistent with existing project conventions.

---

## Slide 8: What Worked / What Needed a Human

**Agent handled well:**
- Reading and comprehending a large existing codebase
- Following established patterns (copied IP core style from BiquadFilter)
- Cross-domain work (VHDL ↔ Python ↔ TCL build system)
- Responding to design feedback and updating coherently
- Auto-generating documentation

**Required human judgment:**
- Architecture decisions (new module vs. modify in place)
- Algorithm correctness (anti-windup semantics, thresholds)
- Catching missed conventions (review found missing patterns)
- Deciding what to test and how to verify

**The AI accelerates implementation; the engineer owns the design.**

---

## Slide 9: Practical Tips

1. **Write an AGENTS.md** — biggest ROI for AI-assisted development
2. **Use plan mode** — get alignment on approach before code is generated
3. **Iterate on design** — treat it as a design conversation, not one-shot
4. **Review everything** — fast code still needs the same scrutiny
5. **Track plans in the repo** — enables multi-session work and handoffs
6. **Stay in your domain** — the agent is a force multiplier, not a substitute for understanding the system

---

## Demo Script (if doing live)

1. Show the initial prompt and explain AGENTS.md context (~60s)
2. Show the plan output and one design Q&A exchange (~60s)
3. Scroll through the generated VHDL — point out state machine, IP cores (~60s)
4. Show the Python driver + CLI integration (~30s)
5. Show one review catch (missing FluxQuantum pattern) and the fix (~30s)
6. Summarize: what worked, what needed human input (~60s)
