# ECC AI Seminar Demo — Use Case 2: AI-Assisted Feature Addition

**Presenter:** Ben Reese  
**Time:** ~5 minutes  
**Tool:** Claude Code (Anthropic CLI agent)

## Slide 1: Title

**AI-Assisted Feature Addition To Existing Code**  
Generative AI Use Case 2  
Ben Reese

## Slide 2: The Task

**Converting a Fixed-Point PID Controller to Floating Point**

- Warm TDM: real-time SQUID readout system for TES detector arrays
- AdcDsp module: PID servo loop running at 125 MHz on Kintex-7 FPGA
- 8 parallel instances, each maintaining state for up to 256 multiplexed rows
- Goal: replace 24-bit fixed-point math with IEEE 754 float32
  - Better dynamic range, simpler coefficient tuning
  - Reuse existing Xilinx FP IP cores already in the design

**Why this is a good AI demo:**
- Large, real codebase (~1000 line VHDL module + Python drivers)
- Requires understanding existing architecture before designing new code
- Cross-cuts firmware (VHDL) and software (Python) layers
- Not a greenfield task — must integrate with existing infrastructure

## Slide 3: The Workflow (Overview)

**Claude Code operates in the terminal alongside your normal tools**

1. **Explore** — Agent reads the codebase, understands architecture
2. **Plan** — Proposes approach, asks clarifying questions
3. **Implement** — Writes code across multiple files simultaneously  
4. **Iterate** — Responds to feedback, fixes issues
5. **Document** — Creates plan docs and progress tracking

All within a single conversational session (~30 minutes of interaction)

## Slide 4: Prompt → Exploration

**Initial prompt (paraphrased):**
> "Let's focus on the ColumnFpgaBoard325Coordinator10G target. The AdcDsp
> block implements a fixed-point PID. I'd like to adapt it to use floating
> point math. The design already has some FP IP cores. Make a plan."

**AGENTS.md — the codebase map for AI:**

The repo contains an `AGENTS.md` file at the root that provides:
- Project summary and architecture overview (data flow, timing, clocks)
- Repository layout with directory purposes
- Key entities table (entity → file → role)
- "Essential Reading by Task" — tells the agent where to start for DSP work
- Naming conventions, build system patterns, platform details
- Available AI skills (domain-specific review tools)

This is the **single most impactful thing** you can add to a repo for AI
assistance. Without it, the agent spends many turns guessing file locations
and misunderstanding conventions. With it, the agent immediately knows:
- Where DSP code lives (`firmware/common/warm_tdm/rtl/`)
- How builds work (ruckus, Vivado, generics pattern)
- What packages to import, what naming to follow
- How Python drivers map to firmware registers

**AGENTS.md snippets to show on slide:**

```
### Data Flow (Column Board)

AD9681 ADC → DataPath → AdcDsp (PID + baseline + flux-jump) → EventBuilder → PGP Stream → Host
                                    ↕
                          FastDacDriver (SQ1 feedback)
```

```
| Entity   | Path                    | Role                                        |
|----------|-------------------------|---------------------------------------------|
| DataPath | DataPath.vhd            | ADC interface + DSP pipeline instantiation   |
| AdcDsp   | AdcDsp.vhd              | Per-column PID loop, baseline, flux-jump     |
| ...      | ...                     | ...                                          |
```

```
| Task Area        | Start With These Files                                      |
|------------------|-------------------------------------------------------------|
| DSP / data path  | DataPath.vhd, AdcDsp.vhd, BiquadFilter.vhd, EventBuilder.vhd |
```

```
## Firmware Conventions
- **Library**: All RTL loaded as `-lib warm_tdm`
- **VHDL standard**: 2008 (`-fileType "VHDL 2008"`)
- **Generics**: Suffixed `_G` (e.g., `TPD_G`, `SIMULATION_G`)
- **Constants**: Suffixed `_C`
- **Architecture**: Always named `rtl`
```

**What the agent did with this context:**
- Spawned 3 parallel search agents to explore the codebase
- Found existing FpMac (4-cycle FMA) and Int2Fp IP cores in BiquadFilter.vhd
- Mapped the full instantiation hierarchy (8 instances in DataPath.vhd)
- Identified resource budget (DSP48 at 8%, BRAM at 59%, slices at 75%)
- Analyzed timing constraints (125 MHz, WNS = 0.038 ns)

**Key takeaway:** AGENTS.md turns a cold-start exploration into a guided one.
The agent built a complete understanding of the architecture in under a minute.

## Slide 4b: AGENTS.md → Plan Docs

**AGENTS.md also directs how work is tracked:**

```
For substantial feature work, keep planning, progress, and handoff Markdown
under `docs/plans/<task-name>/`. See `docs/plans/README.md`
for the file layout and lifecycle.
```

The agent automatically created `docs/plans/fp-dsp-pid/PLAN.md` and
`PROGRESS.md` following this convention — no extra prompting needed.

**Snippet from the generated PLAN.md:**

```markdown
# Floating-Point PID (AdcDspFp)

## Scope
Convert the AdcDsp PID servo loop from fixed-point to IEEE 754 single-
precision floating-point arithmetic. The new module (AdcDspFp.vhd) is
port-compatible with AdcDsp and selectable via a USE_FLOAT_PID_G generic.

## Architecture

| Core          | Operation   | Latency  |
|---------------|-------------|----------|
| FpMac (exist) | A*B+C       | 4 cycles |
| Int2Fp (exist)| int → float | 2 cycles |
| Fp2Int (new)  | float → int | 2 cycles |
```

```markdown
## Key Design Decisions

1. Track unwrapped sq1FbFull as primary state — eliminates awkward
   reconstruction step. BiquadFilter receives smooth float directly.
2. Float pass-through to BiquadFilter — INPUT_IS_FLOAT_G generic skips
   BiquadFilter's Int2Fp, saving 2 cycles and 8 IP instances.
3. Iterative flux jump — simple integer loop handles multi-quantum jumps.
```

**Why this matters:**
- Plans survive context resets (agent can resume work in a new session)
- Other engineers can review the approach before code is written
- Decisions are captured alongside the rationale, not buried in chat

**Note:** This example was small enough to fit in one session/context window.
Most real features are not — they span multiple sessions, days, or engineers.
Plan and progress docs become essential for continuity in those cases.
Good practice to track regardless of size.

## Slide 5: Plan → Iteration

**Agent proposed a plan, then I asked questions:**

- "Should we make a new module or modify in place?" → New module (AdcDspFp.vhd)
- "Can we pass float directly to the biquad filter?" → Yes, add INPUT_IS_FLOAT_G
- "How does anti-windup work in float domain?" → Sign-bit check, no extra FP op
- "Can we support multi-quantum flux jumps?" → Yes, iterative integer loop

**The plan evolved through dialogue:**
- Started with simple IP core reuse
- Added float pass-through to BiquadFilter (eliminates 8 redundant conversions)
- Simplified flux jump logic (track unwrapped value as primary state)
- Designed for future FP16 configurability

## Slide 6: Implementation Output

**Files created/modified in one session:**

| File | Action | Lines |
|------|--------|-------|
| `AdcDspFp.vhd` | Created | ~600 |
| `Fp2Int.xci` | Created | IP core definition |
| `_AdcDspFp.py` | Created | ~130 |
| `DataPath.vhd` | Modified | +30 (generate blocks) |
| `BiquadFilter.vhd` | Modified | +15 (float bypass) |
| `WarmTdmPkg.vhd` | Modified | +10 (stream config) |
| `ColumnFpgaBoard.vhd` | Modified | +2 (generic) |
| `ruckus.tcl` | Modified | +1 |
| `_ArgParser.py` | Modified | +7 (CLI flag) |
| `_DataPath.py` | Modified | +8 (conditional instantiation) |
| + 5 more files | Modified | Threading `--floatPid` through SW stack |

**~800 lines of production code** across firmware and software layers.

## Slide 7: What Worked Well

- **Architecture comprehension** — correctly identified IP core reuse pattern
  from BiquadFilter, RAM width implications, timing budget
- **Cross-domain** — handled VHDL, Python, Vivado IP, and TCL build system
- **Iterative design** — responded to design feedback (anti-windup, flux jumps,
  multi-quantum support) and updated the plan coherently
- **Convention adherence** — followed existing SLAC FPGA patterns (VHDL style,
  register interface, PyRogue device patterns, ruckus build system)
- **Documentation** — created plan/progress docs automatically

## Slide 8: What Required Human Judgment

- **Architecture decisions** — new module vs. in-place modification
- **Algorithm correctness** — anti-windup semantics, flux jump thresholds
- **System integration** — which target to enable, how to thread CLI flags
- **Verification strategy** — what to test, acceptance criteria
- **Review** — caught missing RowPidStatus, FluxQuantum LinkVariable pattern

**The AI accelerates implementation; the engineer owns the design.**

## Slide 9: Practical Tips

1. **Give context upfront** — describe the system, point to key files
2. **Use plan mode** — get alignment before code is written
3. **Ask questions back** — the agent will ask good clarifying questions if prompted
4. **Iterate on design** — treat it as a conversation, not a one-shot prompt
5. **Review everything** — the agent makes reasonable code but misses conventions
6. **Commit incrementally** — don't let it accumulate too many uncommitted changes

---

## Demo Script (if doing live)

1. Show the initial prompt and the exploration phase (~30s)
2. Show the plan output and one Q&A exchange (~60s)
3. Show the generated AdcDspFp.vhd state machine (~60s)
4. Show the Python driver and CLI integration (~30s)
5. Show the DataPath.vhd generate block change (~30s)
6. Summarize: what worked, what needed human input (~60s)
