# Understand — code in, recognized aspects out

The mirror direction. Paste a Python loop and press **Run**: the engine recognizes what the loop **builds**,
one statement at a time — the value-building *aspects* it can prove (accumulate a running value, collect into
a container, set an index), and the honest **residual** it cannot name (a side effect, plain control flow).
It never guesses a loop's whole intent; it proves the aspects it can and leaves the rest explicit.

This is the understanding half of the thesis: recognition is **partial and per-aspect**, which is what turns a
~4% "whole-loop idiom" hit rate into ~52% of real loops having a recognized value-aspect — while staying
honest (an aspect under a guard is tagged `(cond)`, never reported as unconditional). It is pure AST — the
code is **not executed**.

*(First run downloads the engine into your browser — a few seconds, one time.)*

<div class="ps-playground" data-mode="understand" markdown="0">
  <div class="ps-field">
    <label>Python — a loop (or several)</label>
    <textarea class="ps-code ps-code-input" spellcheck="false">total = 0
out = []
seen = {}
for x in xs:
    total += x                 # accumulate a running sum
    if x > 0:
        out.append(x)          # collect the positives (under a guard)
    seen[x] = True             # index-set
    print(x)                   # side effect — honest residual</textarea>
  </div>
  <div class="ps-knobs">
    <button class="ps-run" type="button">Run ▶</button>
  </div>
  <div class="ps-out"></div>
</div>

Try a plain summing loop (`s = 0; for x in xs: s += x`) — one clean `accumulate`. Try a comprehension-shaped
`for x in xs: out.append(f(x))` — one `collect`. Try a compound loop that does several things at once — it is
recognized as the *set* of aspects it has, with everything else named as residual, not swept under the rug.

For where this reaches and where it plateaus (measured over the Python standard library), see
[Understanding findings](understanding_findings.md).
