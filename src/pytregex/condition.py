#!/usr/bin/env python3

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generator, Iterable, Iterator, List, NamedTuple, Optional

from .exceptions import ParseException

if TYPE_CHECKING:
    from .relation import AbstractRelationData
    from .tree import Tree


class NamedNodes:
    def __init__(self, name: Optional[str], nodes: Optional[List["Tree"]], string_repr: str = "") -> None:
        self.name = name
        self.nodes = nodes
        self.string_repr = string_repr

    def set_name(self, new_name: Optional[str]) -> None:
        self.name = new_name

    def set_nodes(self, new_nodes: List["Tree"]) -> None:
        self.nodes = new_nodes


class NodeDescription(NamedTuple):
    op: type["NODE_OP"]
    value: str

    def __repr__(self) -> str:
        return self.value


@dataclass
class BackRef:
    node_descriptions: "NodeDescriptions"
    nodes: Optional[list["Tree"]]


class NodeDescriptions:
    def __init__(
        self,
        *node_descriptions: NodeDescription,
        under_negation: bool = False,
        use_basic_cat: bool = False,
        condition: Optional["And"] = None,
        backref: Optional[BackRef] = None,
        name: Optional[str] = None,
    ) -> None:
        self.descriptions = list(node_descriptions)
        self.under_negation = under_negation
        self.use_basic_cat = use_basic_cat

        self.condition = condition
        self.backref = backref
        self.name = name

    def __iter__(self) -> Iterator[NodeDescription]:
        return iter(self.descriptions)

    def __repr__(self) -> str:
        if self.name is not None:
            ret = f"={self.name}"
        else:
            prefix = f"{'!' if self.under_negation else ''}{'@' if self.use_basic_cat else ''}"
            ret = f"{prefix}{'|'.join(map(str, self.descriptions))}"

        if self.condition is not None:
            ret = f"({ret} {self.condition})"
        return ret

    def set_backref(
        self,
        backref: BackRef,
        name: str,
    ) -> None:
        self.backref = backref
        self.name = name

    def set_condition(self, condition: "AbstractCondition") -> None:
        if self.condition is None:
            self.condition = And(condition)
        else:
            self.condition.append_condition(condition)

    def add_description(self, other_description: NodeDescription) -> None:
        self.descriptions.append(other_description)

    def negate(self) -> bool:
        if self.under_negation:
            return False

        self.under_negation = True
        return True

    def enable_basic_cat(self) -> bool:
        if self.use_basic_cat:
            return False

        self.use_basic_cat = True
        return True

    def _satisfies_ignore_condition(self, t: "Tree"):
        return any(
            desc.op.satisfies(
                t, desc.value, under_negation=self.under_negation, use_basic_cat=self.use_basic_cat
            )
            for desc in self.descriptions
        )

    def satisfies(self, t: "Tree") -> bool:
        if self.condition is None:
            return any(
                desc.op.satisfies(
                    t, desc.value, under_negation=self.under_negation, use_basic_cat=self.use_basic_cat
                )
                for desc in self.descriptions
            )
        else:
            cond_satisfies = self.condition.satisfies
            return any(
                desc.op.satisfies(
                    t, desc.value, under_negation=self.under_negation, use_basic_cat=self.use_basic_cat
                )
                and cond_satisfies(t)
                for desc in self.descriptions
            )

    def searchNodeIterator(self, t: "Tree", *, recursive: bool = True) -> Generator["Tree", None, None]:
        node_gen = t.preorder_iter() if recursive else (t for _ in range(1))
        node_gen = filter(self._satisfies_ignore_condition, node_gen)

        if self.condition is None:
            ret = node_gen
        else:
            # complains about duplicate names in conjunction
            if self.name is not None and self.name in self.condition.names:
                raise ParseException(
                    f"Variable '{self.name}' was declared twice in the scope of the same conjunction."
                )

            cond_search = self.condition.searchNodeIterator
            ret = (m for node in node_gen for m in cond_search(node))

        if self.backref is not None:
            ret = list(ret)
            if self.backref.nodes is not None:
                self.backref.nodes.extend(ret)
            else:
                self.backref.nodes = ret
        yield from ret


class NODE_OP(ABC):
    @classmethod
    @abstractmethod
    def satisfies(
        cls,
        node: "Tree",
        value: str = "",
        *,
        under_negation: bool = False,
        use_basic_cat: bool = False,
    ) -> bool:
        raise NotImplementedError()

    @classmethod
    def in_(
        cls,
        node: "Tree",
        ids: Iterable[str],
        *,
        under_negation: bool = False,
        use_basic_cat: bool = False,
    ) -> bool:
        return any(
            cls.satisfies(node, id, under_negation=under_negation, use_basic_cat=use_basic_cat) for id in ids
        )


class NODE_ID(NODE_OP):
    @classmethod
    def satisfies(
        cls, node: "Tree", id: str, *, under_negation: bool = False, use_basic_cat: bool = False
    ) -> bool:
        attr = "basic_category" if use_basic_cat else "label"
        value = getattr(node, attr)

        if value is None:
            return under_negation
        else:
            return (value == id) != under_negation


class NODE_REGEX(NODE_OP):
    @classmethod
    def satisfies(
        cls, node: "Tree", regex: str, *, under_negation: bool = False, use_basic_cat: bool = False
    ) -> bool:
        attr = "basic_category" if use_basic_cat else "label"
        value = getattr(node, attr)

        if value is None:
            return under_negation
        else:
            # Convert regex to standard python regex
            flag = ""
            current_flag = regex[-1]
            while current_flag != "/":
                # Seems that only (?m) and (?x) are useful for node describing:
                #  re.ASCII      (?a)
                #  re.IGNORECASE (?i)
                #  re.LOCALE     (?L)
                #  re.DOTALL     (?s)
                #  re.MULTILINE  (?m)
                #  re.VERBOSE    (?x)
                if current_flag not in "xi":
                    raise ValueError(f"Error!! Unsupported regexp flag: {current_flag}")
                flag += current_flag
                regex = regex[:-1]
                current_flag = regex[-1]

            regex = regex[1:-1]
            if flag:
                regex = "(?" + "".join(set(flag)) + ")" + regex

            return (re.search(regex, value) is not None) != under_negation


class NODE_ANY(NODE_OP):
    @classmethod
    def satisfies(
        cls,
        node: "Tree",
        value: str = "",
        *,
        under_negation: bool = False,
        use_basic_cat: bool = False,
    ) -> bool:
        return not under_negation


class NODE_ROOT(NODE_OP):
    @classmethod
    def satisfies(
        cls,
        node: "Tree",
        value: str = "",
        *,
        under_negation: bool = False,
        use_basic_cat: bool = False,
    ) -> bool:
        return (node.parent is None) != under_negation


class AbstractCondition(ABC):
    @abstractmethod
    def __repr__(self):
        raise NotImplementedError

    def satisfies(self, t: "Tree") -> bool:
        try:
            next(self.searchNodeIterator(t))
        except StopIteration:
            return False
        else:
            return True

    @abstractmethod
    def searchNodeIterator(self, t: "Tree") -> Generator["Tree", None, None]:
        raise NotImplementedError

class Condition(AbstractCondition):
    def __init__(
        self,
        relation_data: "AbstractRelationData",
        node_descriptions: NodeDescriptions,
    ) -> None:
        self.relation_data = relation_data
        self.node_descriptions = node_descriptions

    def __repr__(self):
        return f"{self.relation_data} {self.node_descriptions}"

    def searchNodeIterator(self, t: "Tree") -> Generator["Tree", None, None]:
        for _ in self.relation_data.searchNodeIterator(t, self.node_descriptions):
            yield t


# ----------------------------------------------------------------------------
#                                   Logic


class AbstractLogicCondition(AbstractCondition):
    ...


class And(AbstractCondition):
    def __init__(self, *conds: AbstractCondition):
        self.conditions = list(conds)

        self.names: set[str] = set()
        # map(self.check_name, conds)
        for cond in conds:
            self.check_name(cond)

    def check_name(self, cond: AbstractCondition):
        if isinstance(cond, (Not, Opt)):
            return self.check_name(cond.condition)
        elif isinstance(cond, Condition):
            if (name := getattr(cond.node_descriptions, "name", None)) is None:
                return
            if name in self.names:
                raise ParseException(
                    f"Variable '{name}' was declared twice in the scope of the same conjunction."
                )
            else:
                self.names.add(name)
        elif isinstance(cond, (And, Or)):
            comm = cond.names & self.names
            if comm:
                raise ParseException(
                    f"Variable '{comm.pop()}' was declared twice in the scope of the same conjunction."
                )
            else:
                self.names.update(cond.names)
        else:
            assert False, f"Unexpected condition type: {type(cond)}"

    def __repr__(self):
        return " ".join(map(str, self.conditions))

    def searchNodeIterator(self, t: "Tree") -> Generator["Tree", None, None]:
        candidates = (t,)
        for condition in self.conditions:
            candidates = tuple(
                node for candidate in candidates for node in condition.searchNodeIterator(candidate)
            )
        yield from candidates

    def append_condition(self, other_condition: AbstractCondition):
        self.check_name(other_condition)
        self.conditions.append(other_condition)

    def extend_conditions(self, other_conditions: Iterable[AbstractCondition]):
        for cond in other_conditions:
            self.check_name(cond)
        # map(self.check_name, other_conditions)
        self.conditions.extend(other_conditions)


class Or(AbstractCondition):
    def __init__(self, *conds: AbstractCondition):
        self.conditions = list(conds)
        self.names: set[str] = set()
        for cond in conds:
            self.store_name(cond)
        # map(self.store_name, conds)

    def store_name(self, cond: AbstractCondition):
        if isinstance(cond, (Not, Opt)):
            return self.store_name(cond.condition)
        elif isinstance(cond, (Condition)):
            if (name := getattr(cond.node_descriptions, "name", None)) is None:
                return
            self.names.add(name)
        elif isinstance(cond, (And, Or)):
            self.names.update(cond.names)
        else:
            assert False, f"Unexpected condition type: {type(cond)}"

    def __repr__(self):
        return f"[ {' || '.join(map(str, self.conditions))} ]"

    def searchNodeIterator(self, t: "Tree") -> Generator["Tree", None, None]:
        for condition in self.conditions:
            yield from condition.searchNodeIterator(t)

    def append_condition(self, other_condition):
        self.conditions.append(other_condition)
        self.store_name(other_condition)

    def extend_conditions(self, other_conditions):
        self.conditions.extend(other_conditions)
        for cond in other_conditions:
            self.store_name(cond)
        # map(self.store_name, other_conditions)


class Not(AbstractCondition):
    def __init__(self, condition: AbstractCondition):
        self.condition = condition

    def __repr__(self):
        return f"!{self.condition}"

    def searchNodeIterator(self, t: "Tree") -> Generator["Tree", None, None]:
        try:
            next(self.condition.searchNodeIterator(t))
        except StopIteration:
            yield t
        else:
            return


class Opt(AbstractCondition):
    def __init__(self, condition: AbstractCondition):
        self.condition = condition

    def __repr__(self):
        return f"?[{self.condition}]"

    def searchNodeIterator(self, t: "Tree") -> Generator["Tree", None, None]:
        g = self.condition.searchNodeIterator(t)
        try:
            node = next(g)
        except StopIteration:
            yield t
        else:
            yield node
            yield from g


"""
echo '(foo bar (rab (baz bar)))' | python -m pytregex 'foo=a <bar=a << baz=a' -filter -h a

echo '(foo bar (rab (baz bar)))' | python -m pytregex 'foo <bar=a << baz ' -filter -h a
echo '(foo bar (rab (baz bar)))' | tregex.py 'foo <bar=a << baz ' -filter -h a

echo '(foo bar (rab baz))' | python -m pytregex 'foo ![ <ba=z || << baz=r ]' -filter
echo '(foo bar (rab baz))' | tregex.py 'foo ![ <ba | << baz ]' -filter

echo '(foo bar (rab baz))' | python -m pytregex 'foo [ <bar || << baz ]' -filter
echo '(foo bar (rab baz))' | tregex.py 'foo [ <bar | << baz ]' -filter

echo '(foo )' | python -m pytregex 'foo=a $ bar=a' -filter

echo '(T (X (N (N Moe (PNT ,)))) (NP (X (N Curly)) (NP (CONJ and) (X (N Larry)))))' | python -m pytregex 'PNT=p >>- (__=l >, (__=t <- (__=r <, __=m <- (__ <, CONJ <- __=z))))' -filter -h m
echo '(T (X (N (N Moe (PNT ,)))) (NP (X (N Curly)) (NP (CONJ and) (X (N Larry)))))' | tregex.py 'PNT=p >>- (__=l >, (__=t <- (__=r <, __=m <- (__ <, CONJ <- __=z))))' -filter -h m

echo '(T (X (N (N Moe (PNT ,)))) (NP (X (N Curly)) (NP (CONJ and) (X (N Larry)))))' | python -m pytregex '(__=r <, __=m <- (__ <, CONJ <- __=z))' -filter -h m
echo '(T (X (N (N Moe (PNT ,)))) (NP (X (N Curly)) (NP (CONJ and) (X (N Larry)))))' | tregex.py '(__=r <, __=m <- (__ <, CONJ <- __=z))' -filter -h m

echo '(T (X (N (N Moe (PNT ,)))) (NP (X (N Curly)) (NP (CONJ and) (X (N Larry)))))' | python -m pytregex '(__=r <- (__ <, CONJ <- __=z) <, __=m)' -filter -h m
echo '(T (X (N (N Moe (PNT ,)))) (NP (X (N Curly)) (NP (CONJ and) (X (N Larry)))))' | tregex.py '(__=r <- (__ <, CONJ <- __=z) <, __=m)' -filter -h m


echo '(A (B 1) (C 2) (B 3))' | python -m pytregex 'A ?[< B=foo || < C=foo]' -filter
"""
