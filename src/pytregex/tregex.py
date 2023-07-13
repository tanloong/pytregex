# /home/tan/.local/share/stanford-tregex-2020-11-17/stanford-tregex-4.2.0-sources/edu/stanford/nlp/trees/tregex/Relation.java
import logging
import re
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    Union,
    NamedTuple,
)

from ply import lex, yacc
from relation import Relation
from tree import Tree


class NamedNodes(NamedTuple):
    name: Optional[str]
    nodes: List[Tree]


class ReducedRelation(NamedTuple):
    relation: str
    modifier: Optional[str]


class ReducedRelationWithStrArg(NamedTuple):
    relation: str
    modifier: Optional[str]
    arg: List[Tree]


class ReducedRelationWithNumArg(NamedTuple):
    relation: str
    modifier: Optional[str]
    arg: int


MODIFIER = Optional[str]
AND_CONDITION = Tuple[Callable, NamedNodes, MODIFIER]
AND_CONDITION_W_REL_ARG = Tuple[Callable, NamedNodes, MODIFIER, List[Tree]]
AND_CONDITIONS = Tuple[Union[AND_CONDITION, AND_CONDITION_W_REL_ARG]]


class TregexMatcherBase:  # {{{
    @classmethod
    def match_condition(
        cls,
        this_node: Tree,
        this_name: Optional[str],
        those: NamedNodes,
        modifier: MODIFIER,
        condition_func: Callable,
    ) -> Tuple[int, dict]:
        if modifier is None:
            match_count, backrefs_map = cls._exactly_match_condition(
                this_node, this_name, those, condition_func
            )
        elif modifier == "!":
            match_count, backrefs_map = cls._not_match_condition(
                this_node, those, condition_func
            )
        else:
            match_count, backrefs_map = cls._optionally_match_condition(
                this_node, those, condition_func
            )
        return (match_count, backrefs_map)

    @classmethod
    def _exactly_match_condition(
        cls,
        this_node: Tree,
        this_name: Optional[str],
        those: NamedNodes,
        condition_func: Callable[[Tree, Tree], bool],
    ) -> Tuple[int, dict]:
        that_name, those_nodes = those

        backrefs_map: Dict[str, list] = {}
        # for "A=x < B=x", only map x to B
        if this_name is not None and this_name == that_name:
            this_name = None

        for name in (this_name, that_name):
            if name is not None:
                backrefs_map[name] = []

        match_count = 0
        for that_node in those_nodes:
            if condition_func(this_node, that_node):
                for name, node in ((this_name, this_node), (that_name, that_node)):
                    if name is not None:
                        backrefs_map[name].append(node)
                match_count += 1

        return (match_count, backrefs_map)

    @classmethod
    def _not_match_condition(
        cls,
        this_node: Tree,
        those: NamedNodes,
        condition_func: Callable,
    ) -> Tuple[int, dict]:
        _, those_nodes = those

        match_count = 0
        if all(
            map(
                lambda that_node, this_node=this_node: not condition_func(this_node, that_node),  # type: ignore
                those_nodes,
            )
        ):
            match_count += 1
        return (match_count, {})

    @classmethod
    def _optionally_match_condition(
        cls,
        this_node: Tree,
        those: NamedNodes,
        condition_func: Callable[[Tree, Tree], bool],
    ) -> Tuple[int, dict]:
        that_name, those_nodes = those

        if that_name is None:
            return (1, {})

        backrefs_map: Dict[str, list] = {}
        backrefs_map[that_name] = []
        for that_node in those_nodes:
            if condition_func(this_node, that_node):
                backrefs_map[that_name].append(that_node)
        return (1, backrefs_map)


# }}}
class TregexMatcher(TregexMatcherBase):
    @classmethod
    def match_any(cls, trees: List[Tree]) -> Generator[Tree, Any, None]:
        for tree in trees:
            for node in tree.preorder_iter():
                yield node

    @classmethod
    def match_or_nodes(
        cls, trees: List[Tree], or_nodes: List[str], is_negate: bool = False
    ) -> Generator[Tree, Any, None]:
        def condition_func(candidate, or_nodes) -> bool:
            return (candidate in or_nodes) != is_negate

        if or_nodes[0] == "@":
            attr = "basic_category"
            or_nodes.pop(0)
        else:
            attr = "label"

        for tree in trees:
            for node in tree.preorder_iter():
                if condition_func(getattr(node, attr), or_nodes):
                    yield node

    @classmethod
    def match_regex(
        cls, trees: List[Tree], regex: str, is_negate: bool = False
    ) -> Generator[Tree, Any, None]:
        pattern = re.compile(regex)
        for tree in trees:
            for node in tree.preorder_iter():
                if node.label is None:
                    if is_negate:
                        yield node
                    continue

                if (pattern.search(node.label) is None) == is_negate:
                    yield node

    @classmethod
    def and_(
        cls,
        this_node: Tree,
        this_name: Optional[str],
        and_conditions: Tuple[Union[AND_CONDITION, AND_CONDITION_W_REL_ARG]],
    ) -> Tuple[int, dict]:
        match_count = 1
        backrefs_map: Dict[str, list] = {}

        for func, those, modifier, *arg in and_conditions:
            assert modifier in (None, "!", "?")
            match_count_cur_cond, backrefs_map_cur_cond = cls.match_condition(
                this_node,
                this_name,
                those,
                modifier,
                lambda this_node, that_node: func(this_node, that_node, *arg),
            )
            if match_count_cur_cond == 0:
                return (0, {})

            match_count *= match_count_cur_cond
            for name, node_list in backrefs_map_cur_cond.items():
                if backrefs_map.get(name) is not None:
                    logging.warning(
                        f'You gave different nodes the same name "{name}" in a single chain of'
                        " and_conditions! Only the last node given that name will be"
                        " remembered."
                    )
                backrefs_map[name] = node_list

        return (match_count, backrefs_map)

    @classmethod
    def or_(
        cls,
        these_nodes: List[Tree],
        this_name: Optional[str],
        or_conditions: Tuple[AND_CONDITIONS],
    ) -> Tuple[List[Tree], dict]:
        res: List[Tree] = []
        backrefs_map: Dict[str, list] = {}

        for this_node in these_nodes:
            for and_conditions in or_conditions:
                match_count, backrefs_map_cur_conds = cls.and_(
                    this_node, this_name, and_conditions
                )

                res += [this_node for _ in range(match_count)]
                for name, node_list in backrefs_map_cur_conds.items():
                    backrefs_map[name] = backrefs_map.get(name, []) + node_list
        return (res, backrefs_map)


class TregexPattern:
    tokens = [  # {{{
        "REGEX",
        "BLANK",
        "REL_W_STR_ARG",
        "RELATION",
        "NOT",
        "OPTIONAL",
        "AND",
        "OR_NODE",
        "OR_REL",
        "LPAREN",
        "RPAREN",
        "LBRACKET",
        "RBRACKET",
        "EQUAL",
        "AT",
        "NUMBER",
        "ID",
        "TERMINATOR",
    ]
    # tokens = ['VARNAME',]

    t_BLANK = r"__"

    RELATION_MAP = {
        "<": Relation.parent_of,
        ">": Relation.child_of,
        "<<": Relation.dominates,
        ">>": Relation.dominated_by,
        ">:": Relation.only_child_of,
        "<:": Relation.has_only_child,
        ">`": Relation.last_child_of_parent,
        ">-": Relation.last_child_of_parent,
        "<`": Relation.parent_of_last_child,
        "<-": Relation.parent_of_last_child,
        ">,": Relation.leftmost_child_of,
        "<,": Relation.has_leftmost_child,
        "<<`": Relation.has_rightmost_descendant,
        "<<-": Relation.has_rightmost_descendant,
        ">>`": Relation.rightmost_descendant_of,
        ">>-": Relation.rightmost_descendant_of,
        ">>,": Relation.leftmost_descendant_of,
        "<<,": Relation.has_leftmost_descendant,
        "$..": Relation.left_sister_of,
        "$++": Relation.left_sister_of,
        "$--": Relation.right_sister_of,
        "$,,": Relation.right_sister_of,
        "$.": Relation.immediate_left_sister_of,
        "$+": Relation.immediate_left_sister_of,
        "$-": Relation.immediate_right_sister_of,
        "$,": Relation.immediate_right_sister_of,
        "$": Relation.sister_of,
        "==": Relation.equals,
        "<=": Relation.parent_equals,
        "<<:": Relation.unary_path_ancestor_of,
        ">>:": Relation.unary_path_descedant_of,
        ":": Relation.pattern_splitter,
        ">#": Relation.immediately_heads,
        "<#": Relation.immediately_headed_by,
        ">>#": Relation.heads,
        "<<#": Relation.headed_by,
        "..": Relation.precedes,
        ",,": Relation.follows,
        ".": Relation.immediately_precedes,
        ",": Relation.immediately_follows,
        "<<<": Relation.ancestor_of_leaf,
    }

    REL_W_STR_ARG_MAP = {
        "<+": Relation.unbroken_category_dominates,
        ">+": Relation.unbroken_category_is_dominated_by,
        ".+": Relation.unbroken_category_precedes,
        ",+": Relation.unbroken_category_follows,
    }

    REL_W_NUM_ARG_MAP = {
        ">": Relation.ith_child_of,
        ">-": Relation.ith_child_of,
        "<": Relation.has_ith_child,
        "<-": Relation.has_ith_child,
    }
    # make sure long relations are checked first, or otherwise `>>` might
    # be tokenized as two `>`s.
    rels = sorted(RELATION_MAP.keys(), key=len, reverse=True)
    # add negative lookahead assertion to ensure ">+" is seen as REL_W_STR_ARG instead of RELATION(">") and ID("+")
    t_RELATION = r"(?:" + "|".join(map(re.escape, rels)) + r")(?!\+)"
    rels_w_arg = sorted(REL_W_STR_ARG_MAP.keys(), key=len, reverse=True)
    t_REL_W_STR_ARG = "|".join(map(re.escape, rels_w_arg))
    # REL_W_NUM_ARG don't have to be declared, as > and < have already been as t_RELATION

    t_NOT = r"!"
    t_OPTIONAL = r"\?"
    t_AND = r"&"  # in `NP < NN | < NNS & > S`, `&` takes precedence over `|`
    t_OR_REL = r"\|\|"
    t_OR_NODE = r"\|"
    t_LPAREN = r"\("
    t_RPAREN = r"\)"
    t_LBRACKET = r"\["
    t_RBRACKET = r"\]"
    t_EQUAL = r"="
    t_AT = r"@"
    t_NUMBER = r"[0-9]+"
    t_ID = r"[^ 0-9\n\r(/|@!#&)=?[\]><~_.,$:{};][^ \n\r(/|@!#&)=?[\]><~.$:;]*"
    t_TERMINATOR = r";"
    t_ignore = " \r\t"

    def t_REGEX(self, t):
        r"/[^/\n\r]*/[ix]*"
        flag = ""
        while t.value[-1] != "/":
            flag += t.value[-1]
            t.value = t.value[:-1]

        t.value = t.value[1:-1]
        if flag:
            t.value = "(?" + "".join(set(flag)) + ")" + t.value
        return t

    def t_error(self, t):
        logging.critical("Tokenization error: Illegal character '%s'" % t.value[0])
        raise SystemExit()

    def __init__(self, tregex_pattern: str):
        self.lexer = lex.lex(module=self)
        self.lexer.input(tregex_pattern)

        self.backrefs_map: Dict[str, list] = {}
        self.pattern = tregex_pattern

    def findall(self, tree_string: str) -> List[Tree]:
        trees = Tree.from_string(tree_string)
        parser = self.make_parser(trees)
        self._reset_lexer_state()
        return parser.parse(lexer=self.lexer)

    def _reset_lexer_state(self):
        """
        reset lexer.lexpos to make the lexer reusable
        https://github.com/dabeaz/ply/blob/master/doc/ply.md#internal-lexer-state
        """
        self.lexer.lexpos = 0

    def make_parser(self, trees: List[Tree]):
        tokens = self.tokens

        precedence = (
            ("left", "OR_REL"),
            # keep consistency with Stanford Tregex
            # 1. "VP < NP < N" matches a VP which dominates both an NP and an N
            # 2. "VP < (NP < N)" matches a VP dominating an NP, which in turn dominates an N
            ("left", "RELATION", "AND"),
            # https://github.com/dabeaz/ply/issues/215
            ("left", "IMAGINE"),
            ("nonassoc", "EQUAL"),
        )  # }}}

        # 1. Label description
        # 1.1 simple label description
        def p_id(p):
            """
            or_nodes : ID
            """
            logging.debug("following rule: or_nodes -> ID")
            p[0] = [p[1]]

        def p_or_or_nodes(p):
            """
            or_nodes : OR_NODE or_nodes
            """
            logging.debug("following rule: or_nodes -> OR_NODE or_nodes")
            p[0] = p[2]

        def p_or_nodes_or_nodes(p):
            """
            or_nodes : or_nodes or_nodes
            """
            logging.debug("following rule: or_nodes -> or_nodes or_nodes")
            p[1].extend(p[2])
            p[0] = p[1]

        def p_at_or_nodes(p):
            """
            or_nodes : AT or_nodes
            """
            logging.debug("following rule: or_nodes -> AT or_nodes")
            p[2].insert(0, p[1])
            p[0] = p[2]

        def p_lparen_or_nodes_rparen(p):
            """
            or_nodes : LPAREN or_nodes RPAREN
            """
            logging.debug("following rule: or_nodes -> LPAREN or_nodes RPAREN")
            p[0] = p[2]

        def p_or_nodes(p):
            """
            node_obj_list : or_nodes
            """
            logging.debug("following rule: node_obj_list -> or_nodes")
            p[0] = NamedNodes(
                None,
                list(TregexMatcher.match_or_nodes(trees, p[1], is_negate=False)),
            )

        def p_not_or_nodes(p):
            """
            node_obj_list : NOT or_nodes
            """
            logging.debug("following rule: node_obj_list -> NOT or_nodes")
            p[0] = NamedNodes(
                None, list(TregexMatcher.match_or_nodes(trees, p[2], is_negate=True))
            )

        def p_regex(p):
            """
            node_obj_list : REGEX
            """
            logging.debug("following rule: node_obj_list -> REGEX")
            p[0] = NamedNodes(
                None,
                list(node for node in TregexMatcher.match_regex(trees, p[1], is_negate=False)),
            )

        def p_not_regex(p):
            """
            node_obj_list : NOT REGEX
            """
            logging.debug("following rule: or_nodes -> NOT REGEX")
            p[0] = NamedNodes(
                None,
                list(node for node in TregexMatcher.match_regex(trees, p[2], is_negate=True)),
            )

        def p_blank(p):
            """
            node_obj_list : BLANK
            """
            logging.debug("following rule: node_obj_list -> BLANK")
            p[0] = NamedNodes(None, list(TregexMatcher.match_any(trees)))

        def p_node_obj_list_equal_id(p):
            """
            node_obj_list : node_obj_list EQUAL ID
            """
            logging.debug("following rule: or_nodes -> or_nodes EQUAL ID")
            name = p[3]
            nodes = p[1].nodes
            self.backrefs_map[name] = nodes

            p[0] = NamedNodes(name, nodes)

        def p_lparen_node_obj_list_rparen(p):
            """
            node_obj_list : LPAREN node_obj_list RPAREN
            """
            logging.debug("following rule: node_obj_list -> LPAREN node_obj_list RPAREN")
            p[0] = p[2]

        # --------------------------------------------------------
        # 2. relation
        # 2.1 RELATION
        def p_relation(p):
            """
            reduced_relation : RELATION
            """
            logging.debug("following rule: reduced_relation -> RELATION")
            p[0] = ReducedRelation(p[1], None)

        def p_not_relation(p):
            """
            reduced_relation : NOT RELATION
            """
            logging.debug("following rule: reduced_relation -> NOT RELATION")
            p[0] = ReducedRelation(p[2], "!")

        def p_optional_relation(p):
            """
            reduced_relation : OPTIONAL RELATION
            """
            logging.debug("following rule: reduced_relation -> OPTIONAL RELATION")
            p[0] = ReducedRelation(p[2], "?")

        # 2.2 REL_W_STR_ARG
        def p_rel_w_str_arg_lparen_node_obj_list_rparen(p):
            """
            reduced_rel_w_str_arg : REL_W_STR_ARG LPAREN node_obj_list RPAREN
            """
            logging.debug(
                "following rule: reduced_rel_w_str_arg -> REL_W_STR_ARG LPAREN node_obj_list"
                " RPAREN"
            )
            # relation=p[1], modifier=None, arg=p[3].nodes
            p[0] = ReducedRelationWithStrArg(p[1], None, p[3].nodes)

        def p_not_rel_w_str_arg_lparen_node_obj_list_rparen(p):
            """
            reduced_rel_w_str_arg : NOT REL_W_STR_ARG LPAREN node_obj_list RPAREN
            """
            logging.debug(
                "following rule: reduced_rel_w_str_arg -> NOT REL_W_STR_ARG LPAREN node_obj_list"
                " RPAREN"
            )
            # relation=p[2], modifier=None, arg=p[4].nodes
            p[0] = ReducedRelationWithStrArg(p[2], "!", p[4].nodes)

        def p_optional_rel_w_str_arg_lparen_node_obj_list_rparen(p):
            """
            reduced_rel_w_str_arg : OPTIONAL REL_W_STR_ARG LPAREN node_obj_list RPAREN
            """
            logging.debug(
                "following rule: reduced_rel_w_str_arg -> OPTIONAL REL_W_STR_ARG LPAREN"
                " node_obj_list RPAREN"
            )
            # relation=p[2], modifier=None, arg=p[4].nodes
            p[0] = ReducedRelationWithStrArg(p[2], "?", p[4].nodes)

        # 2.3 REL_W_NUM_ARG
        def p_relation_number(p):
            """
            reduced_rel_w_num_arg : RELATION NUMBER
            """
            logging.debug("following rule: reduced_rel_w_num_arg -> RELATION NUMBER")
            rel, num = p[1:]
            if rel.endswith("-"):
                num = f"-{num}"
            p[0] = ReducedRelationWithNumArg(rel, None, int(num))

        def p_not_relation_number(p):
            """
            reduced_rel_w_num_arg : NOT RELATION NUMBER
            """
            logging.debug("following rule: reduced_rel_w_num_arg -> NOT RELATION NUMBER")
            rel, num = p[2:]
            if rel.endswith("-"):
                num = f"-{num}"
            p[0] = ReducedRelationWithNumArg(rel, "!", int(num))

        def p_optional_relation_number(p):
            """
            reduced_rel_w_num_arg : OPTIONAL RELATION NUMBER
            """
            rel, num = p[2:]
            if rel.endswith("-"):
                num = f"-{num}"
            logging.debug("following rule: reduced_rel_w_num_arg -> OPTIONAL RELATION NUMBER")
            p[0] = ReducedRelationWithNumArg(rel, "?", int(num))

        # 3. chain description
        # --------------------------------------------------------
        def p_reduced_relation_node_obj_list(p):
            """
            and_conditions : reduced_relation node_obj_list %prec IMAGINE
            """
            logging.debug("following rule: and_conditions -> reduced_relation node_obj_list")
            # %prec IMAGINE: https://github.com/dabeaz/ply/issues/215
            (rel, modifier), those = p[1:]
            p[0] = [
                (self.RELATION_MAP[rel], those, modifier),
            ]

        def p_reduced_rel_w_str_arg_node_obj_list(p):
            """
            and_conditions : reduced_rel_w_str_arg node_obj_list %prec IMAGINE
            """
            logging.debug(
                "following rule: and_conditions -> reduced_rel_w_str_arg node_obj_list %prec"
                " IMAGINE"
            )
            # %prec IMAGINE: https://github.com/dabeaz/ply/issues/215
            (rel_w_str_arg, modifier, rel_arg), those_nodes = p[1:]
            p[0] = [
                (self.REL_W_STR_ARG_MAP[rel_w_str_arg], those_nodes, modifier, rel_arg),
            ]

        def p_reduced_rel_w_num_arg_node_obj_list(p):
            """
            and_conditions : reduced_rel_w_num_arg node_obj_list %prec IMAGINE
            """
            logging.debug(
                "following rule: and_conditions -> reduced_rel_w_num_arg node_obj_list %prec"
                " IMAGINE"
            )
            # %prec IMAGINE: https://github.com/dabeaz/ply/issues/215
            (rel_w_num_arg, modifier, rel_arg), those_nodes = p[1:]
            p[0] = [
                (self.REL_W_NUM_ARG_MAP[rel_w_num_arg], those_nodes, modifier, rel_arg),
            ]

        # --------------------------------------------------------
        def p_and_and_conditions(p):
            """
            and_conditions : AND and_conditions
            """
            logging.debug("following rule: and_conditions -> AND and_conditions")
            p[0] = p[2]

        def p_or_conditions_and_conditions(p):
            """
            and_conditions : and_conditions and_conditions
            """
            logging.debug("following rule: and_conditions -> and_conditions and_conditions")
            p[1].extend(p[2])
            p[0] = p[1]

        def p_and_condition(p):
            """
            or_conditions : and_conditions
            """
            logging.debug("following rule: or_conditions -> and_conditions")
            p[0] = [
                p[1],
            ]

        def p_or_conditions_or_or_conditions(p):
            """
            or_conditions : or_conditions OR_REL or_conditions
            """
            logging.debug("following rule: or_conditions -> or_conditions OR_REL or_conditions")
            p[1].extend(p[3])
            p[0] = p[1]

        def p_or_conditions(p):
            """
            chain : or_conditions
            """
            logging.debug("following rule: chain -> or_conditions")
            p[0] = p[1]

        def p_lparen_chain_rparen(p):
            """
            chain : LPAREN chain RPAREN
            """
            logging.debug("following rule: chain -> LPAREN chain RPAREN")
            p[0] = p[2]

        def p_lbracket_chain_rbracket(p):
            """
            chain : LBRACKET chain RBRACKET
            """
            logging.debug("following rule: chain -> LBRACKET chain RBRACKET")
            p[0] = p[2]

        def p_node_obj_list_chain(p):
            """
            node_obj_list : node_obj_list chain
            """
            logging.debug("following rule: node_obj_list -> node_obj_list chain")
            (this_name, these_nodes), or_conditions = p[1:]
            res, backrefs_map = TregexMatcher.or_(these_nodes, this_name, or_conditions)
            for name, node_list in backrefs_map.items():
                logging.debug(
                    "Mapping {} to nodes:\n  {}".format(
                        name, "\n  ".join(node.to_string() for node in node_list)
                    )
                )
                self.backrefs_map[name] = node_list

            p[0] = NamedNodes(this_name, res)

        def p_node_obj_list(p):
            """
            pattern : node_obj_list
            """
            logging.debug("following rule: pattern -> node_obj_list")
            p[0] = p[1].nodes

        def p_pattern(p):
            """
            patterns : pattern
                     | pattern TERMINATOR
            """
            logging.debug("following rule: patterns -> pattern")
            p[0] = p[1]

        def p_pattern_pattern(p):
            """
            patterns : patterns pattern
                     | patterns pattern TERMINATOR
            """
            logging.debug("following rule: patterns -> patterns pattern")
            p[1].extend(p[2])
            p[0] = p[1]

        def p_error(p):
            if p:
                logging.critical(
                    f"{self.lexer.lexdata}\n{' ' * p.lexpos}˄\nParsing error at token"
                    f" '{p.value}'"
                )
            else:
                logging.critical("Parsing Error at EOF")
            raise SystemExit()

        return yacc.yacc(debug=True, start="patterns")
