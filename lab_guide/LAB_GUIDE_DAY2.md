# myAGV Summer School — Day 2 Lab Guide

**Phases covered:** Phase 2 — Autonomous Navigation · Phase 3 — Human-in-the-loop Delivery

> **Pre-requisite:** Day 1 (Phase 1 SLAM) is complete.
> You do **not** need API keys for any exercise in this guide.

---

## Setup

Activate the virtual environment once at the start of each session:

```bash
cd ~/myagv_lab_project/myagv_lab
source .venv/bin/activate
```

All commands below assume the venv is active and you are in the `myagv_lab/` directory.

---

## Overview

| Phase | What the robot does | New concept |
|-------|---------------------|-------------|
| **2** | Follows named waypoints on the saved map | Waypoint navigation, path planning |
| **3** | Plans a delivery task in PDDL, navigates autonomously, pauses to ask you to load/unload the package | Task planning (PDDL), LLM translation, human-robot collaboration |

---

## Part 1 — Phase 2: Autonomous Navigation

### 1.1 Background

In Day 1 the robot built an occupancy-grid map by scanning the environment.
Today it will **use that map** to navigate autonomously.

The key idea is **waypoint navigation**:
- The map is divided into named locations: `home`, `loading_area`, `delivery_area`, `storage_area`, `charger_station`.
- Given a destination name, the robot finds a collision-free path and drives there.
- In simulation this is handled entirely in Python by `SimRobot` — no ROS2 required.

The central class is `NavigationManager` in [phase2_nav/nav_node.py](myagv_lab/phase2_nav/nav_node.py).
Its API is one line:

```python
result = nav.navigate("delivery_area")   # returns NavResult(success, message)
```

### 1.2 The Waypoint Registry

Open [phase2_nav/nav_node.py](myagv_lab/phase2_nav/nav_node.py) and find `WAYPOINTS` (around line 53):

```python
WAYPOINTS: dict[str, Pose2D] = {
    "home":            Pose2D(0.4, 0.6,  0.0),
    "loading_area":    Pose2D(0.8, 0.4,  0.0),
    "delivery_area":   Pose2D(2.0, 0.4,  math.radians(90)),
    "storage_area":    Pose2D(5.0, 0.4,  math.radians(180)),
    "charger_station": Pose2D(7.0, 0.4,  math.radians(270)),
}
```

`Pose2D(x, y, yaw)` — `x` and `y` are in metres on the map; `yaw` is the robot's
facing direction in radians (0 = east, π/2 = north, π = west).

### 1.3 Interactive Demo

```bash
python3 -m myagv_lab.phase2_nav.nav_node --sim
```

You will see a numbered menu in the terminal:

```
Available destinations:
  1. home                  (0.4, 0.6)
  2. loading_area          (0.8, 0.4)
  3. delivery_area         (2.0, 0.4)
  4. storage_area          (5.0, 0.4)
  5. charger_station       (7.0, 0.4)
  q. Quit
```

Select a number.  The robot navigates and the ASCII map re-renders, marking
the path (`○`), start (`S`), and goal (`G`).

### 1.4 Live Matplotlib Visualiser

```bash
python3 -m myagv_lab.phase2_nav.nav_viz
```

A matplotlib window opens showing:

- **Dark cells** — walls / obstacles
- **Light cells** — free space
- **Purple circles** — named waypoints
- **Red arrow** — robot position and heading
- **Blue trail** — path taken so far
- **Orange star** — departure point, **green diamond** — current goal

The demo automatically visits `loading_area → delivery_area → storage_area → home`.
Watch the trail build up with each leg of the journey.

---

### 1.5 Exercises — Phase 2

**Exercise 2.1 — Understand the path**

Run the interactive demo. Navigate `home → delivery_area`, then `delivery_area → home`.

Answer in your lab notebook:
1. How many simulation steps did each trip take?
2. Did the robot take the same path both ways? Why or why not?

---

**Exercise 2.2 — Add a new waypoint**

Add `"inspection_area"` to `WAYPOINTS` in [phase2_nav/nav_node.py](myagv_lab/phase2_nav/nav_node.py):

```python
"inspection_area": Pose2D(3.5, 2.0, 0.0),
```

Re-run the interactive demo — your new waypoint should appear in the menu and on the ASCII map.

---

**Exercise 2.3 — Write a scripted route**

Find `run_scripted_demo()` in `nav_node.py`. Change the sequence to include your new waypoint:

```python
sequence = ["loading_area", "inspection_area", "delivery_area", "home"]
```

Run it:

```bash
python3 -m myagv_lab.phase2_nav.nav_node --scripted
```

---

**Exercise 2.4 — Graceful failure**

Create a small script `test_nav.py` and try navigating to a non-existent location:

```python
import os; os.environ["MYAGV_USE_SIM"] = "1"
from myagv_lab.phase2_nav.nav_node import NavigationManager

nav = NavigationManager()
result = nav.navigate("moon_base")
print(result.success, result.message)
```

Run it:
```bash
python3 test_nav.py
```

Observe the error message. Now open `NavigationManager.navigate()` and add a
`print()` warning so the unknown location is reported clearly before returning.

---

**Exercise 2.5 — Live visualiser with your route**

Open [phase2_nav/nav_viz.py](myagv_lab/phase2_nav/nav_viz.py) and change the
`sequence` list in `main()` to match your Exercise 2.3 route.
Run it and take a screenshot of the matplotlib window for your report.

---

## Part 2 — Phase 3: Human-in-the-loop Delivery

### 2.1 Background

Phase 3 introduces the **full delivery pipeline** for the first time:

```
You type a task in natural language
           │
           ▼  llm_translator.py  (DeepSeek LLM)
  PDDL domain + problem
           │
           ▼  pddl_solver.py  (pyperplan — automatic planner)
  [navigate, load-package, deliver-package, …]
           │
           ▼  primitive_executor.py
  AGV navigates autonomously  +  ★ you are prompted to load / unload packages
```

The **cobot arm is not introduced until Phase 4**.
In Phase 3, whenever the plan requires loading or unloading a package, the
AGV stops and asks **you** to do it manually.  This lets you observe the full
pipeline before any hardware is involved.

### 2.2 Key Concepts

**PDDL — Planning Domain Definition Language**

A formal language for describing:
- **Domain** — what actions the robot can take (navigate, load, deliver, recharge)
- **Problem** — the current state and the goal to achieve

The planner (pyperplan) reads both and produces an ordered list of actions — the **plan**.

The domain for this lab is in [phase4_delivery/pddl_planner/domain.py](myagv_lab/phase4_delivery/pddl_planner/domain.py):

| Action | Precondition | Effect |
|--------|-------------|--------|
| `navigate` | robot is at `from` | robot moves to `to` |
| `load-package` | robot and package both at location | robot holds package |
| `deliver-package` | robot holds package, is at destination | package delivered |
| `recharge` | robot at charger station | robot charged |

**LLM translation**

You describe the task in plain English.  The DeepSeek LLM converts it into a
PDDL *problem* file.  The `--fallback` flag skips the LLM and uses a
pre-written problem — no API key needed.

**HumanCobot**

`HumanCobot` in [phase3_human_cobot/human_cobot.py](myagv_lab/phase3_human_cobot/human_cobot.py)
stands in for the cobot arm.  When `load-package` fires, the terminal prints:

```
★  HUMAN ACTION REQUIRED
   Please place  package_A  onto the AGV platform at the loading area.
   Press Enter when done…
```

Press **Enter** to confirm — the pipeline resumes immediately.

### 2.3 Fallback Scenarios (no API key needed)

Three pre-built scenarios are available with `--fallback`:

| Scenario | Task |
|----------|------|
| `deliver_A` | Load package_A → navigate to delivery area → deliver → return home |
| `deliver_AB` | Deliver two packages, one after the other |
| `recharge_then_deliver` | Recharge at charger station first, then deliver package_A |

**Run `deliver_A` (default):**

```bash
python3 -m myagv_lab.phase3_human_cobot.human_cobot_manager --sim --fallback
```

**With live visualiser:**

```bash
python3 -m myagv_lab.phase3_human_cobot.human_cobot_manager --sim --fallback --viz
```

**Two packages:**

```bash
python3 -m myagv_lab.phase3_human_cobot.human_cobot_manager \
    --sim --fallback --scenario deliver_AB --viz
```

**Recharge then deliver:**

```bash
python3 -m myagv_lab.phase3_human_cobot.human_cobot_manager \
    --sim --fallback --scenario recharge_then_deliver --viz
```

### 2.4 What You Will See

**Terminal output** — the plan is printed before execution:

```
══════════════════════════════════════════════════
  Plan for: [fallback scenario: deliver_A]  (5 steps)
══════════════════════════════════════════════════
  1  navigate        agv home loading_area
  2  load-package    agv arm package_a loading_area
  3  navigate        agv loading_area delivery_area
  4  deliver-package agv package_a delivery_area
  5  navigate        agv delivery_area home
══════════════════════════════════════════════════
```

At each `load-package` / `deliver-package` step the pipeline pauses for your input.
After the mission the timeline is printed:

```
────────────────────────────────────────────────────
  Mission Timeline
────────────────────────────────────────────────────
  t=   0.0s  →  PIPELINE_START
  t=   0.1s  →  PLAN_READY(5_steps)
  t=   0.2s  →  NAVIGATING_TO_LOADING_AREA
  t=   1.3s  →  ARRIVED_AT_LOADING_AREA
  t=   1.3s  →  WAITING_HUMAN
  t=   4.1s  →  HUMAN_CONFIRMED
  ...
────────────────────────────────────────────────────
```

**Visualiser panels** (when `--viz` is passed):

- **Left** — map with live robot position and blue trail
- **Right** — plan step list:
  - Grey = pending · Blue = running · **Yellow ★** = waiting for you · Green ✓ = done · Red ✗ = failed

### 2.5 With LLM Translation

> Requires `STUDENT_ID` and API keys set in `~/.bashrc`.

```bash
python3 -m myagv_lab.phase3_human_cobot.human_cobot_manager --sim \
    --task "Pick up package_A from the loading area and deliver it."
```

With visualiser:

```bash
python3 -m myagv_lab.phase3_human_cobot.human_cobot_manager --sim --viz \
    --task "First recharge the robot, then deliver package_A."
```

---

### 2.6 Exercises — Phase 3

**Exercise 3.1 — Read the plan**

Run `deliver_A` without the visualiser so you can read the full terminal output:

```bash
python3 -m myagv_lab.phase3_human_cobot.human_cobot_manager --sim --fallback
```

Answer in your lab notebook:
1. How many steps are in the plan?
2. What is the first action? What is the last?
3. Which steps required you to press Enter?

---

**Exercise 3.2 — Compare all three scenarios**

Run all three fallback scenarios.  For each, copy the plan steps into your notebook.

- How does `deliver_AB` differ from `deliver_A`?
- What extra step appears in `recharge_then_deliver`, and where in the sequence?

---

**Exercise 3.3 — Explore the PDDL domain**

Open [phase4_delivery/pddl_planner/domain.py](myagv_lab/phase4_delivery/pddl_planner/domain.py)
and find the `load-package` action.

Answer:
1. What are its **preconditions**? (What must be true before it can execute?)
2. What are its **effects**? (What changes after it executes?)
3. Why can `navigate` appear multiple times in a plan without any precondition about cargo?

---

**Exercise 3.4 — Write your own task (LLM mode)**

> Requires API keys.  If not available, skip to Exercise 3.5.

Try two different natural language descriptions and compare the plans produced:

```bash
python3 -m myagv_lab.phase3_human_cobot.human_cobot_manager --sim \
    --task "Go to the loading area, pick up package_A, bring it to delivery, and come back."

python3 -m myagv_lab.phase3_human_cobot.human_cobot_manager --sim \
    --task "The robot needs charging. After charging, deliver package_A."
```

Questions:
1. Do both produce the same plan?
2. What happens if you ask for something the domain cannot handle, e.g. `"Make coffee"`?

---

**Exercise 3.5 — Trace the pipeline**

Add a `print()` statement between each stage in
[phase3_human_cobot/human_cobot_manager.py](myagv_lab/phase3_human_cobot/human_cobot_manager.py):

- After Stage 1: print the raw PDDL problem string
- After Stage 2: print the plan list

Run any fallback scenario and observe how data transforms at each stage.

---

**Exercise 3.6 — Add a new PDDL action (stretch goal)**

Open [phase4_delivery/pddl_planner/domain.py](myagv_lab/phase4_delivery/pddl_planner/domain.py)
and add an `inspect` action:

```lisp
(:action inspect
  :parameters (?r - robot ?l - location)
  :precondition (and
    (at ?r ?l)
  )
  :effect (and
    (inspected ?l)
  )
)
```

Also add the `(inspected ?l - location)` predicate to the `:predicates` block.

Then add a handler in
[phase4_delivery/pddl_planner/primitive_executor.py](myagv_lab/phase4_delivery/pddl_planner/primitive_executor.py)
that prints `"Inspecting …"` when the action fires.

> Hint: search for how `recharge` is handled in `_dispatch()`.

---

## Summary

| Concept | Where to find it |
|---------|-----------------|
| Waypoint coordinates | `phase2_nav/nav_node.py` → `WAYPOINTS` |
| Navigation API | `phase2_nav/nav_node.py` → `NavigationManager` |
| Live nav visualiser | `phase2_nav/nav_viz.py` → `NavVisualizer` |
| PDDL domain (all actions) | `phase4_delivery/pddl_planner/domain.py` |
| LLM → PDDL translation | `phase4_delivery/pddl_planner/llm_translator.py` |
| PDDL solver (pyperplan) | `phase4_delivery/pddl_planner/pddl_solver.py` |
| Plan → robot commands | `phase4_delivery/pddl_planner/primitive_executor.py` |
| Human cobot | `phase3_human_cobot/human_cobot.py` → `HumanCobot` |
| Phase 3 manager | `phase3_human_cobot/human_cobot_manager.py` → `HumanMissionManager` |
| Phase 3 visualiser | `phase3_human_cobot/human_cobot_viz.py` → `HumanCobotVisualizer` |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: pyperplan` | Run `source .venv/bin/activate` first |
| `Missing environment variables: ['LANGFUSE_HOST']` | Add API keys to `~/.bashrc` and run `source ~/.bashrc` |
| `Missing environment variables: ['STUDENT_ID']` | `export STUDENT_ID="yourlastname"` (lowercase) |
| `ValueError: No plan found` | The task may be unsolvable with the current domain — try `--fallback` |
| Matplotlib window freezes | Do not click inside the figure while it is animating |
