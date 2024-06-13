#!/usr/bin/env python3

import re
from abc import ABC, abstractmethod
from collections import namedtuple
from typing import TYPE_CHECKING, Callable, Generator, Iterable, Iterator, List, NamedTuple, Optional

from relation import AbstractRelation
from tree import Tree

if TYPE_CHECKING:
    from pytregex.condition import AbstractCondition


class NamedNodes:
    def __init__(self, name: Optional[str], nodes: Optional[List[Tree]], string_repr: str = "") -> None:
        self.name = name
        self.nodes = nodes
        self.string_repr = string_repr

    def set_name(self, new_name: Optional[str]) -> None:
        self.name = new_name

    def set_nodes(self, new_nodes: List[Tree]) -> None:
        self.nodes = new_nodes


class NodeDescription(NamedTuple):
    op: type["NODE_OP"]
    value: str


class NodeDescriptions:
    def __init__(
        self,
        node_descriptions: List[NodeDescription],
        *,
        is_negated: bool = False,
        use_basic_cat: bool = False,
    ) -> None:
        self.descriptions = node_descriptions
        self.is_negated = is_negated
        self.use_basic_cat = use_basic_cat

        self.name = None
        self.__repr = "".join(desc.value for desc in self.descriptions)
        self.condition: "AbstractCondition" | None = None

    def __iter__(self) -> Iterator[NodeDescription]:
        return iter(self.descriptions)

    def __repr__(self) -> str:
        return self.__repr

    def has_name(self) -> bool:
        return self.name is not None

    def set_name(self, name: str) -> None:
        self.name = name

    def set_condition(self, condition: "AbstractCondition") -> None:
        self.condition = condition
        self.__repr = "({} {})".format("".join(desc.value for desc in self.descriptions), str(condition))

    def add_description(self, other_description: NodeDescription) -> None:
        self.descriptions.append(other_description)

        self.__repr = f"{self.__repr}|{other_description.value}"

    def toggle_negated(self) -> None:
        self.is_negated = not self.is_negated
        self.__repr = f"!{self.__repr}"

    def set_use_basic_cat(self) -> None:
        self.use_basic_cat = True
        self.__repr = f"@{self.__repr}"

    def _satisfies_ignore_condition(self, t: Tree):
        return any(
            desc.op.satisfies(t, desc.value, is_negated=self.is_negated, use_basic_cat=self.use_basic_cat)
            for desc in self.descriptions
        )

    def satisfies(self, t: Tree) -> bool:
        if self.condition is None:
            return any(
                desc.op.satisfies(t, desc.value, is_negated=self.is_negated, use_basic_cat=self.use_basic_cat)
                for desc in self.descriptions
            )
        else:
            cond_satisfies = self.condition.satisfies
            return any(
                desc.op.satisfies(t, desc.value, is_negated=self.is_negated, use_basic_cat=self.use_basic_cat)
                and cond_satisfies(t)
                for desc in self.descriptions
            )

    def searchNodeIterator(self, t: Tree, *, recursive: bool = True) -> Generator[Tree, None, None]:
        node_gen = t.preorder_iter() if recursive else (t for _ in range(1))
        if self.condition is None:
            yield from (node for node in node_gen if self._satisfies_ignore_condition(node))
        else:
            cond_search = self.condition.searchNodeIterator
            for node in filter(self._satisfies_ignore_condition, node_gen):
                yield from cond_search(node)


class NODE_OP(ABC):
    @classmethod
    @abstractmethod
    def satisfies(
        cls,
        node: Tree,
        value: str = "",
        *,
        is_negated: bool = False,
        use_basic_cat: bool = False,
    ) -> bool:
        raise NotImplementedError()

    @classmethod
    def in_(
        cls,
        node: Tree,
        ids: Iterable[str],
        *,
        is_negated: bool = False,
        use_basic_cat: bool = False,
    ) -> bool:
        return any(cls.satisfies(node, id, is_negated=is_negated, use_basic_cat=use_basic_cat) for id in ids)


class NODE_ID(NODE_OP):
    @classmethod
    def satisfies(cls, node: Tree, id: str, *, is_negated: bool = False, use_basic_cat: bool = False) -> bool:
        attr = "basic_category" if use_basic_cat else "label"
        value = getattr(node, attr)

        if value is None:
            return is_negated
        else:
            return (value == id) != is_negated


class NODE_REGEX(NODE_OP):
    @classmethod
    def satisfies(
        cls, node: Tree, regex: str, *, is_negated: bool = False, use_basic_cat: bool = False
    ) -> bool:
        attr = "basic_category" if use_basic_cat else "label"
        value = getattr(node, attr)

        if value is None:
            return is_negated
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

            return (re.search(regex, value) is not None) != is_negated


class NODE_ANY(NODE_OP):
    @classmethod
    def satisfies(
        cls,
        node: Tree,
        value: str = "",
        *,
        is_negated: bool = False,
        use_basic_cat: bool = False,
    ) -> bool:
        return not is_negated


class NODE_ROOT(NODE_OP):
    @classmethod
    def satisfies(
        cls,
        node: Tree,
        value: str = "",
        *,
        is_negated: bool = False,
        use_basic_cat: bool = False,
    ) -> bool:
        return (node.parent is None) != is_negated
