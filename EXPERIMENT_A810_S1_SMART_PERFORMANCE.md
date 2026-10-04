# A810 S1 Smart Performance — internal build

This branch is an internal performance experiment based on the frozen
Drnas-Turnip S1 A810 stack plus the S1H recent-weighted histogram.

## User control

The only switch needed for this experiment is:

`TU_FRANE_SMART=1` — default, Smart Performance enabled.

`TU_FRANE_SMART=0` — disables the new history-first memoization layer and
returns decision ownership to the existing S1 path.

The older S1 safety/performance layers remain compiled in and keep their tested
defaults. No other variable is required for normal testing.

## The idea: Mesa rp_history becomes scene memory

Turnip already keeps a table keyed by render-pass history. Instead of treating
every recurrence as a fresh decision, Smart Performance uses each history row
as a small scene memory:

| History state | Evidence | Pathway behavior | Loser probe | Winner refresh |
|---|---:|---|---:|---:|
| COLD | <4/8 confidence | normal S1 learn/scan | S1 owns it | S1 owns it |
| WARM | 4–5/8, >=8 recent pairs | reuse measured winner | 1/64 | 1/32 |
| TRUSTED | 6–7/8, >=12 recent pairs | hold winner through noise | 1/128 | 1/64 |
| LOCKED | 8/8, >=16 recent pairs | memoized fast decision | 1/256 | 1/128 |

A V57 tail-risk pass cannot use WARM; it needs at least TRUSTED evidence.

## Why it should help frametime

A stable scene no longer repeatedly enters the expensive evidence-completion
path after it has already proven a winner. Most hot recurrences become a few
integer checks plus one deterministic probe mask.

The saved work is not expected to create huge average-FPS gains by itself.
The target is lower selector churn, fewer forced measurements and less
GMEM/SYSMEM flip-flop in recurring scenes.

## Scene-change escape hatches

History never becomes permanent:

- strong opposite V58 learner evidence releases the cached winner immediately;
- strong opposite live Mesa PROFILED evidence releases it;
- repeated winner switches demote the history to a more cautious tier;
- sparse loser probes remain active;
- sparse winner refresh measurements keep the recent histogram moving;
- the S1H histogram periodically halves recent bins, allowing a new regime to
  replace older evidence.

No frame list is stored and nothing is written to disk. Memory is session-local
and bounded by Mesa's existing render-pass history lifecycle.

## Safety

This patch does not modify GMEM allocation/offsets, attachment programming,
LRZ, barriers, shaders, MSAA/resolve rules or Vulkan synchronization. It only
changes when an already-valid GMEM/SYSMEM choice is reused.
