# Advanced Taskwarrior & Timewarrior Configuration

This directory contains a comprehensive, advanced configuration for Taskwarrior and Timewarrior with custom UDAs, contexts, reports, hooks, extensions, and integrations.

## Installation

The configuration is installed at `/realm/project/sinnix/dots/` and symlinked to the appropriate locations:

```bash
# Taskwarrior
~/.taskrc -> /realm/project/sinnix/dots/taskwarrior/taskrc

# Timewarrior
~/.config/timewarrior/timewarrior.cfg -> /realm/project/sinnix/dots/timewarrior/timewarrior.cfg
~/.config/timewarrior/extensions/ -> contains custom extensions
```

Data is stored in standard locations:
- Taskwarrior: `~/.task/`
- Timewarrior: `~/.local/share/timewarrior/`

## Taskwarrior Features

### User Defined Attributes (UDAs)

| UDA | Type | Values | Description |
|-----|------|--------|-------------|
| `estimate` | duration | - | Estimated time to complete |
| `actual` | duration | - | Actual time spent |
| `reviewed` | date | - | Last review date |
| `energy` | string | low, medium, high | Energy level required |
| `impact` | string | low, medium, high, critical | Impact of the task |
| `complexity` | string | trivial, simple, moderate, complex | Task complexity |
| `size` | numeric | - | Size/effort estimate |

**Usage:**
```bash
task add "Implement feature X" estimate:2h energy:high impact:high complexity:moderate
task 1 modify actual:2.5h
```

### Contexts

Pre-configured contexts for different work modes:

- `work` - Work-related tasks
- `home` - Home tasks
- `errands` - Errands and shopping
- `online` / `offline` - Based on connectivity
- `coding` - Development tasks
- `writing` - Writing and documentation
- `learning` - Learning and study
- `review` - Tasks needing review (not reviewed in last 7 days)
- `deep` - High-energy tasks (not tagged 'next')
- `quick` - Low-energy or quick tasks (<15min)

**Usage:**
```bash
task context work    # Activate work context
task @work           # Shorthand
task context none    # Deactivate context
```

### Custom Reports

#### `next` - Most Urgent Tasks
Shows the most urgent pending tasks with detailed information.
```bash
task next
```

#### `overdue` - Overdue Tasks
```bash
task overdue
```

#### `waiting` - Tasks Waiting on Something
```bash
task waiting
```

#### `someday` - Someday/Maybe Tasks
For tasks tagged with `+someday` (GTD-style).
```bash
task someday
```

#### `review` - Tasks Needing Review
Shows tasks that haven't been reviewed in the last 7 days.
```bash
task review
```

#### `weekly` - Weekly Summary
Shows tasks added in the last week.
```bash
task weekly
```

#### `proj` - Project Overview
Overview of tasks by project.
```bash
task proj
```

#### `energy_high` / `energy_low` - Energy-Based Reports
Filter tasks by energy level required.
```bash
task energy_high
task energy_low
```

#### `quickwins` - Quick Wins
High-impact, low-complexity tasks.
```bash
task quickwins
```

#### `full` - Complete View with All UDAs
Shows all task details including UDAs.
```bash
task full
```

### Hooks

Located in `/realm/project/sinnix/dots/taskwarrior/hooks/`:

1. **on-add-inbox.py** - Auto-tags new tasks without a project as `+inbox`
2. **on-modify-review.py** - Updates the `reviewed` UDA when tasks are modified

Hooks are automatically executed by Taskwarrior when enabled in config.

### Aliases

- `task rm` → `task delete`
- `task burndown` → `task burndown.weekly`
- `task dailystatus` → Show tasks completed today
- `task inbox` → Show tasks tagged with `+inbox`
- `task @` → `task context`
- `task +tag` → `task modify +`
- `task -tag` → `task modify -`

### Color Theme

Custom dark 256-color theme with:
- Priority-based coloring (High/Medium/Low)
- Due date indicators (today, overdue)
- Tag-specific colors
- UDA value coloring (energy, impact, complexity)
- Project-specific colors

## Timewarrior Features

### Work Exclusions

Configured to exclude non-work hours:
- **Weekdays (Mon-Fri)**: Before 8:00, lunch 12:00-13:00, after 18:00
- **Weekends (Sat-Sun)**: Before 10:00, after 14:00

These appear as gray blocks in reports.

### Tag Budgets

Pre-configured time budgets for different activities:

| Tag | Budget |
|-----|--------|
| work | 40 hours per week |
| coding | 25 hours per week |
| meetings | 10 hours per week |
| learning | 5 hours per week |
| writing | 5 hours per week |
| admin | 5 hours per week |
| research | 10 hours per week |
| exercise | 5 hours per week |
| reading | 5 hours per week |

Timewarrior will warn when budgets are exceeded.

### Custom Hints

Predefined tag combinations:

```bash
timew start :work       # Tags: work
timew start :dev        # Tags: coding, work
timew start :meeting    # Tags: meetings, work
timew start :learn      # Tags: learning
timew start :personal   # Tags: personal
timew start :break      # Tags: break
```

### Custom Extensions

#### `balance.py` - Work-Life Balance Report

Shows time distribution between work, personal, and other activities:

```bash
timew export :week | python3 ~/.config/timewarrior/extensions/balance.py
```

Output:
- Work time percentage
- Personal time percentage
- Other activities
- Work-life ratio
- Balance assessment

#### `productivity.py` - Productivity Analysis

Analyzes productivity patterns:

```bash
timew export :week | python3 ~/.config/timewarrior/extensions/productivity.py
```

Output:
- Most productive hours of day
- Time by day of week
- Top activities/tags

### Taskwarrior Integration

The `on-modify.timewarrior` hook automatically integrates Taskwarrior with Timewarrior:

1. When you start a task in Taskwarrior (`task 1 start`), Timewarrior starts tracking with the task's tags
2. When you stop or complete a task, Timewarrior stops tracking

**Note**: Currently configured but requires installation in Taskwarrior hooks directory.

## Usage Examples

### GTD Workflow with Taskwarrior

```bash
# Capture
task add "Review quarterly goals" +inbox

# Clarify
task 1 modify project:work priority:H energy:high complexity:moderate estimate:1h

# Organize
task @work

# Review
task review
task 1 modify reviewed:today

# Engage
task next
task context deep     # For high-energy work
task quickwins        # For quick wins
```

### Time Tracking with Timewarrior

```bash
# Start tracking work
timew start :dev "Implementing feature X"

# Check current activity
timew

# Stop tracking
timew stop

# View day summary
timew day

# View week summary with custom reports
timew export :week | python3 ~/.config/timewarrior/extensions/balance.py
timew export :week | python3 ~/.config/timewarrior/extensions/productivity.py

# View summary with tags
timew summary :week :tags

# Track with multiple tags
timew start coding work project-x "Bug fix #123"
```

### Advanced Queries

```bash
# Find high-impact, simple tasks in the coding context
task context coding
task quickwins

# Review all work tasks by energy level
task context work
task energy_high
task energy_low

# Weekly planning
task weekly
task proj

# Track time on specific task
task 5 start
# Timewarrior automatically starts tracking (with integration hook)
task 5 stop
# Timewarrior automatically stops tracking
```

## Configuration Customization

### Adding More UDAs

Edit `/realm/project/sinnix/dots/taskwarrior/taskrc`:

```
uda.myuda.type=string
uda.myuda.label=MyUDA
uda.myuda.values=value1,value2,value3
uda.myuda.default=value1
```

### Creating Custom Reports

```
report.myreport.description=My custom report
report.myreport.columns=id,priority,project,description
report.myreport.labels=ID,P,Proj,Desc
report.myreport.sort=urgency-
report.myreport.filter=status:pending +mytag
```

### Adding Custom Contexts

```
context.mycontext=+tag1 or project:myproject
```

### Modifying Tag Budgets

Edit `/realm/project/sinnix/dots/timewarrior/timewarrior.cfg`:

```
define tags:
  "mytag":
    description = "My custom tag"
    budget = 10 hours per week
```

## Directory Structure

```
/realm/project/sinnix/dots/
├── taskwarrior/
│   ├── taskrc                     # Main taskwarrior config
│   ├── hooks/                     # Custom hooks
│   │   ├── on-add-inbox.py
│   │   └── on-modify-review.py
│   └── themes/
│       └── custom-dark.theme      # Custom color theme
└── timewarrior/
    ├── timewarrior.cfg            # Main timewarrior config
    ├── extensions/                # Custom extensions
    │   ├── on-modify.timewarrior  # Taskwarrior integration
    │   ├── balance.py             # Work-life balance report
    │   └── productivity.py        # Productivity analysis
    └── themes/
        └── custom-dark.theme      # Custom color theme
```

## Troubleshooting

### Taskwarrior hooks not running

Check that hooks are enabled:
```bash
task show hooks
```

Ensure hooks are executable:
```bash
chmod +x /realm/project/sinnix/dots/taskwarrior/hooks/*.py
```

### Timewarrior extensions not found

Verify extensions are in the correct location:
```bash
ls -la ~/.config/timewarrior/extensions/
timew extensions
```

### Configuration not loaded

Check symlinks:
```bash
ls -la ~/.taskrc
ls -la ~/.config/timewarrior/timewarrior.cfg
```

## Further Reading

- **Taskwarrior Documentation**: https://taskwarrior.org/docs/
- **Timewarrior Documentation**: https://timewarrior.net/docs/
- **Tools and Plugins**:
  - https://taskwarrior.org/tools/
  - https://timewarrior.net/tools/
- **tw-hooks Plugin System**: https://github.com/bergercookie/tw-hooks
- **Taskwarrior Kusarigama**: https://github.com/yanick/Taskwarrior-Kusarigama

## Sources

Configuration based on documentation from:
- [Taskwarrior Official Documentation](https://taskwarrior.org/docs/)
- [Timewarrior Official Documentation](https://timewarrior.net/docs/)
- [Taskwarrior Tools](https://taskwarrior.org/tools/)
- [Timewarrior Tools](https://timewarrior.net/tools/)
- [Timewarrior Extensions Guide](https://timewarrior.net/docs/extensions/)
- [tw-hooks](https://github.com/bergercookie/tw-hooks)
- [Taskwarrior Kusarigama](https://github.com/yanick/Taskwarrior-Kusarigama)
