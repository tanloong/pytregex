![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https://raw.githubusercontent.com/tanloong/pytregex/refs/heads/master/pyproject.toml)
[![license](https://img.shields.io/github/license/tanloong/pytregex)](https://github.com/tanloong/pytregex/blob/master/LICENSE)

[Tregex](https://nlp.stanford.edu/software/tregex.html) is the Java program for identifying patterns in constituency trees. PyTregex provides similar functionality in Python.

## Usage

### Command-line

Install it with `pip install` and run it by `python -m pytregex`.

```sh
$ pip install pytregex

$ echo '(NP(DT The)(NN battery)(NN plant))' | python -m pytregex pattern 'NP < NN' -filter
# (NP (DT The) (NN battery) (NN plant))
# (NP (DT The) (NN battery) (NN plant))
# There were 2 matches in total.

$ echo '(NP(DT The)(NN battery)(NN plant))' > trees.txt
$ python -m pytregex pattern 'NP < NN' ./trees.txt
# (NP (DT The) (NN battery) (NN plant))
# (NP (DT The) (NN battery) (NN plant))
# There were 2 matches in total.

$ python -m pytregex pattern 'NP < NN' -C ./trees.txt
# 2

$ python -m pytregex pattern 'NP < NN=a' -h a ./trees.txt
# (NN battery)
# (NN plant)
# There were 2 matches in total.

$ python -m pytregex explain '<'
# 'A < B' means A immediately dominates B

$ python -m pytregex pprint '(NP(DT The)(NN battery)(NN plant))'
# NP
# ├── DT
# │   └── The
# ├── NN
# │   └── battery
# └── NN
#     └── plant
```

### Inline

```python
from pytregex.tregex import TregexPattern

tre = TregexPattern("NP < NN=a")
matches = tre.findall("(NP(DT The)(NN battery)(NN plant))")
handles = tre.get_nodes("a")
print("matches nodes:\n{}\n".format("\n".join(str(m) for m in matches)))
print("named nodes:\n{}".format("\n".join(str(h) for h in handles)))

# Output:
# matches nodes:
# (NP (DT The) (NN battery) (NN plant))
# (NP (DT The) (NN battery) (NN plant))
#
# named nodes:
# (NN battery)
# (NN plant)
```

See [tests](tests/test_tregex.py) for more examples.

## Differences from Tregex

Tregex is whitespace-sensitive, it distinguishes between `|` and `␣|␣`. PyTregex ignores whitespace and has different symbols taking the place of `␣|␣`.

<table>
<tr> <th></th> <th style="text-align: center">Tregex</th> <th style="text-align: center">PyTregex</th> </tr>
<tr>
  <td rowspan="2" style="text-align: left">node disjunction</td>
  <td rowspan="2" style="text-align: center"><code>A|B</code></td>
  <td style="text-align: center"><code>A|B</code></td>
</tr> <tr> <td style="text-align: center"><code>A␣|␣B</code></td> </tr>
<tr>
  <td rowspan="2" style="text-align: left">condition disjunction</td>
  <td rowspan="2" style="text-align: center"><code>A&lt;B␣|␣&lt;C</code></td>
  <td style="text-align: center"><code>A&lt;B␣||␣&lt;C</code></td>
</tr> <tr> <td style="text-align: center"><code>A&lt;B||&lt;C</code></td> </tr>
<tr>
  <td style="text-align: left">expression disjunction</td>
  <td style="text-align: center"><code>A␣|␣B</code></td>
  <td style="text-align: center">N/A</td>
</tr>
<tr>
  <td rowspan="2" style="text-align: left">expression separation</td>
  <td rowspan="2" style="text-align: center">N/A</td>
  <td style="text-align: center"><code>A;B</code></td>
</tr> <tr> <td style="text-align: center"><code>A␣;␣B</code></td> </tr>
</table>

In the table above the difference between expression disjunction and expression separation is whether "expressions stop evaluating as soon as the result is known." For example, in Tregex `NP=a | NNP=b` if `NP` matches, `b` will not be assigned even if there is an `NNP` in the tree, while in PyTregex `NP=a ; NNP=b` assigns `b` as long as `NNP` is found regardless of whether `NP` matches.

## Missing features

### Backreferencing

```sh
$ tree='(NP NP , NP ,)'
$ pattern='(@NP <, (@NP $+ (/,/ $+ (@NP $+ /,/=comma))) <- =comma)' 

$ echo "$tree" | tregex.sh "$pattern" -filter -s 2>/dev/null
# (NP NP , NP ,)

$ echo "$tree" | python -m pytregex pattern "$pattern" -filter
# (@NP <, (@NP $+ (/,/ $+ (@NP $+ /,/=comma))) <- =comma)
#                                              ˄
# Parsing error at token '='
```

### Headfinders

PyTregex currently has only one HeadFinder which is for English. If your patterns are for trees of other languages and contain `<#`, `>#`, `<<#`, or `>>#`, they may not work as expected.

### Variable groups

```sh
$ tree='(SBAR (WHNP-11 (WP who)) (S (NP-SBJ (-NONE- *T*-11)) (VP (VBD resigned))))' 
$ pattern='@SBAR < /^WH.*-([0-9]+)$/#1%index << (__=empty < (/^-NONE-/ < /^\*T\*-([0-9]+)$/#1%index))' 

$ echo "$tree" | tregex.sh "$pattern" -filter 2>/dev/null
# (SBAR
#   (WHNP-11 (WP who))
#   (S
#     (NP-SBJ (-NONE- *T*-11))
#     (VP (VBD resigned))))

$ echo "$tree" | python -m pytregex pattern "$pattern" -filter
# Tokenization error: Illegal character "#"
```

## Acknowledgments

Thanks [Galen Andrew](https://scholar.google.com/citations?user=TNWwJ-UAAAAJ&hl=en), [Roger Levy](https://www.mit.edu/~rplevy/), [Anna Rafferty](https://sites.google.com/site/annanrafferty/), and [John Bauer](https://profiles.stanford.edu/john-bauer) for their work on Tregex. One-third of PyTregex's code is just translated from Tregex.

This program uses [David Beazley](https://www.dabeaz.com/)'s [PLY](https://github.com/dabeaz/ply)(Python Lex-Yacc) for pattern tokenization and parsing.
