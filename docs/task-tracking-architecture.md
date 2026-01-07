# Task Tracking Architecture

## Design Decision: AGENTS.md vs Skills

After consideration, the task tracking protocol is implemented in **AGENTS.md** rather than as a skill, for critical architectural reasons.

## The Problem with Skills

**Skills are NOT guaranteed to be in initial context:**
- New instances see skill exists in available skills list
- But do NOT see the full skill content
- Must explicitly invoke skill or read file to get full guidance
- Depends on `auto_invoke` triggering correctly
- Creates uncertainty: will new instances follow the protocol?

## The Solution: AGENTS.md

**AGENTS.md is ALWAYS in context at conversation start:**
- Every new instance sees it immediately
- No invocation needed
- No dependency on triggers
- Guaranteed baseline behavior
- Part of system prompt for the project

### What Goes Where

```
📄 AGENTS.md (ALWAYS loaded, concise)
├─ Core rules (must tag +claude-work, use instance IDs)
├─ Essential commands (track, annotate, complete)
├─ Ownership verification pattern
├─ Read-only user task interaction
├─ Quick reference
└─ File locations for detailed docs

📎 CLAUDE.md (compatibility symlink)
└─ Points to AGENTS.md for tools that require the filename

📄 dots/ai/instructions/task-tracking.md (expanded reference)
└─ Detailed task tracking protocol

📄 dots/ai/instructions/base.md (expanded reference)
└─ Operational rules and rationale

📚 .claude/skills/task-tracking.md (Invoke when needed, ~500 lines)
├─ Detailed workflow patterns
├─ Complex multi-instance scenarios
├─ Comprehensive examples
├─ Troubleshooting guides
├─ Best practices deep-dives
└─ Edge case handling

📘 .claude/skills/task-tracking-quickstart.md (~100 lines)
├─ Command cheat sheet
├─ Pattern matching table
├─ Decision trees
└─ Muscle memory commands

📖 dots/README-claude-task-tracking.md
└─ User-facing documentation

📖 dots/README-claude-multi-instance-faq.md
└─ Detailed multi-instance scenarios

📜 dots/taskwarrior/claude-helpers-v2.sh
└─ Shell functions for easy tracking
```

## Context Guarantees

### New Instance Startup

**What's GUARANTEED in context:**
```markdown
Contents of /realm/project/sinnix/AGENTS.md (project instructions):
# Repository Guidelines
## Task & Time Tracking Protocol
**ALWAYS ACTIVE**: Use taskwarrior...
[Full AGENTS.md content - ~200 lines]
```

**What's NOT guaranteed:**
- Skill file contents (must invoke)
- Helper script contents (must source)
- README documentation (must read)

### Result

✅ New instance knows:
- MUST tag all tasks with `+claude-work`
- MUST use `project:claude.instance.{id}` naming
- MUST verify ownership before modifying tasks
- HOW to track requests, annotate, complete
- WHERE to find detailed documentation

✅ No ambiguity:
- Not dependent on triggers
- Not dependent on invocation
- Not dependent on file reads
- Core protocol is BASELINE BEHAVIOR

## Layered Documentation Strategy

### Layer 1: AGENTS.md (Operational Protocol)
**Audience**: Claude instances (ALWAYS)
**Purpose**: Core rules that MUST be followed
**Size**: Concise (~150 lines)
**Content**: What, when, how (basics)
**Loading**: Automatic, guaranteed

### Layer 2: Expanded References (On Demand)
**Audience**: Claude instances (ON DEMAND)
**Purpose**: Deep dives, complex scenarios, examples
**Size**: Comprehensive
**Content**: Why, edge cases, patterns, troubleshooting
**Loading**: Explicit file read or skill invocation

Paths:
- `dots/ai/instructions/task-tracking.md`
- `dots/ai/instructions/base.md`
- `.claude/skills/task-tracking.md`

### Layer 3: READMEs (User Documentation)
**Audience**: Human users
**Purpose**: Understanding and customization
**Size**: Detailed (~200-400 lines each)
**Content**: Architecture, FAQ, configuration
**Loading**: User reads when needed

### Layer 4: Helper Scripts
**Audience**: Both (execution)
**Purpose**: Make tracking easy
**Size**: Functional (~300 lines)
**Content**: Shell functions
**Loading**: Explicit source command

## Benefits of This Architecture

### 1. Reliability
- Core protocol ALWAYS present
- No dependency on invocation mechanics
- Guaranteed baseline behavior
- New instances work correctly from start

### 2. Efficiency
- Core protocol is concise (fits in context budget)
- Detailed docs loaded only when needed
- Reduces unnecessary context usage
- Fast startup (no skill loading overhead)

### 3. Clarity
- Clear separation of concerns
- Core rules vs detailed examples
- Operational protocol vs reference documentation
- Easy to understand what's always active

### 4. Maintainability
- Single source of truth for core rules (AGENTS.md)
- Detailed docs can be updated without affecting core
- Skills can be extended without bloating core protocol
- Clear ownership of different documentation layers

### 5. Multi-Instance Support
- Every instance gets same core protocol
- No coordination needed for baseline behavior
- Instance-specific work happens automatically
- Shared understanding across all instances

## Migration from Skill-Based Approach

### Before (Problematic)
```
New Instance Starts
└─> Sees skill in available list
    └─> May or may not invoke skill
        └─> If invoked: Gets full guidance
        └─> If not: Missing core protocol
            └─> ❌ Might not tag +claude-work
            └─> ❌ Might not use instance IDs
            └─> ❌ Might modify user tasks
```

### After (Reliable)
```
New Instance Starts
└─> AGENTS.md automatically loaded
    └─> ✓ Knows to tag +claude-work
    └─> ✓ Knows to use instance IDs
    └─> ✓ Knows ownership verification
    └─> ✓ Has core commands
    └─> Can invoke skill for details if needed
```

## Testing the Architecture

### Test 1: Fresh Instance (No Prior Context)
```
1. Start new Claude conversation in sinnix
2. Verify AGENTS.md is in system context
3. User makes request
4. Verify Claude creates task with:
   - +claude-work tag
   - project:claude.instance.{id}
   - Proper namespacing
```

### Test 2: Multi-Instance Coordination
```
1. Start Instance A
2. Start Instance B
3. Both create tasks
4. Verify:
   - Separate instance IDs
   - No task conflicts
   - Both follow protocol
   - Both can see each other's work
```

### Test 3: User Task Separation
```
1. User creates tasks (no +claude-work)
2. Claude creates tasks (+claude-work)
3. Verify:
   - Claude can read user tasks
   - Claude doesn't modify user tasks
   - Clear separation maintained
```

## Implementation Checklist

- [x] Create AGENTS.md with core protocol
- [x] Update skill to reference AGENTS.md
- [x] Mark skill as reference (auto_invoke: false)
- [x] Update quick-start to reference AGENTS.md
- [x] Keep detailed documentation in skill
- [x] Update helpers to v2 (instance-aware)
- [x] Document architecture decision
- [ ] Test with fresh instance
- [ ] Verify AGENTS.md is in context
- [ ] Confirm baseline behavior

## Future Considerations

### When to Update AGENTS.md
- Core rules change
- Critical bugs in protocol
- New mandatory behaviors
- Essential commands updated

### When to Update Skills
- Adding detailed examples
- New workflow patterns
- Complex scenario documentation
- Troubleshooting guides
- Best practices refinement

### When to Update READMEs
- User-facing changes
- Architecture explanations
- FAQ additions
- Configuration options

## Conclusion

Moving core task tracking protocol to AGENTS.md ensures:
1. **Reliability**: Always in context, no invocation needed
2. **Clarity**: Clear what's mandatory vs optional
3. **Efficiency**: Concise core, detailed docs on demand
4. **Safety**: User tasks protected by guaranteed rules

This architecture solves the "what do new instances know?" problem completely.

**Result**: Every Claude instance in sinnix has the task tracking protocol as baseline operational behavior, not an optional capability.
