#!/usr/bin/env python3

# https://nlp.stanford.edu/nlp/javadoc/javanlp-3.5.0/edu/stanford/nlp/trees/tregex/TregexPattern.html

import warnings


def explain(term):
    if term is None:
        yield from GLOSSARY.values()
    elif term in GLOSSARY:
        yield GLOSSARY[term]
    else:
        warnings.warn(f"Term '{term}' not found in glossary.", stacklevel=1)


GLOSSARY = {
    "<<": "'A << B' means A dominates B",
    ">>": "'A >> B' means A is dominated by B",
    "<": "'A < B' means A immediately dominates B",
    ">": "'A > B' means A is immediately dominated by B",
    "$": "'A $ B' means A is a sister of B (and not equal to B)",
    "..": "'A .. B' means A precedes B",
    ".": "'A . B' means A immediately precedes B",
    ",,": "'A ,, B' means A follows B",
    ",": "'A , B' means A immediately follows B",
    "<<,": "'A <<, B' means B is a leftmost descendant of A",
    "<<-": "'A <<- B' means B is a rightmost descendant of A",
    ">>,": "'A >>, B' means A is a leftmost descendant of B",
    ">>-": "'A >>- B' means A is a rightmost descendant of B",
    "<,": "'A <, B' means B is the first child of A",
    ">,": "'A >, B' means A is the first child of B",
    "<-": "'A <- B' means B is the last child of A",
    ">-": "'A >- B' means A is the last child of B",
    "<`": "'A <` B' means B is the last child of A",
    ">`": "'A >` B' means A is the last child of B",
    "<i": "'A <i B' means B is the iᵗʰ child of A (i > 0)",
    ">i": "'A >i B' means A is the iᵗʰ child of B (i > 0)",
    "<-i": "'A <-i B' means B is the iᵗʰ-to-last child of A (i > 0)",
    ">-i": "'A >-i B' means A is the iᵗʰ-to-last child of B (i > 0)",
    "<:": "'A <: B' means B is the only child of A",
    ">:": "'A >: B' means A is the only child of B",
    "<<:": "'A <<: B' means A dominates B via an unbroken chain (length > 0) of unary local trees.",
    ">>:": "'A >>: B' means A is dominated by B via an unbroken chain (length > 0) of unary local trees.",
    "$++": "'A $++ B' means A is a left sister of B (same as $.. for context-free trees)",
    "$--": "'A $-- B' means A is a right sister of B (same as $,, for context-free trees)",
    "$+": "'A $+ B' means A is the immediate left sister of B (same as $. for context-free trees)",
    "$-": "'A $- B' means A is the immediate right sister of B (same as $, for context-free trees)",
    "$..": "'A $.. B' means A is a sister of B and precedes B",
    "$,,": "'A $,, B' means A is a sister of B and follows B",
    "$.": "'A $. B' means A is a sister of B and immediately precedes B",
    "$,": "'A $, B' means A is a sister of B and immediately follows B",
    "<+(C)": "'A <+(C) B' means A dominates B via an unbroken chain of (zero or more) nodes matching description C",
    ">+(C)": "'A >+(C) B' means A is dominated by B via an unbroken chain of (zero or more) nodes matching description C",
    ".+(C)": "'A .+(C) B' means A precedes B via an unbroken chain of (zero or more) nodes matching description C",
    ",+(C)": "'A ,+(C) B' means A follows B via an unbroken chain of (zero or more) nodes matching description C",
    "<<#": "'A <<# B' means B is a head of phrase A",
    ">>#": "'A >># B' means A is a head of phrase B",
    "<#": "'A <# B' means B is the immediate head of phrase A",
    ">#": "'A ># B' means A is the immediate head of phrase B",
    "==": "'A == B' means A and B are the same node",
    "<=": "'A <= B' means A and B are the same node or A is the parent of B",
    ":": "'A : B' means there is no constraint on the relationship between A and B, this is a pattern-segmenting operator that places",
    "<...": "'A <... { B ; C ; ... }	-- A has exactly B, C, etc as its subtree, with no other children",
}
