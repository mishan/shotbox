"""a11y lint and tree against made-up AT-SPI nodes: an entry named by the
label it is LABELLED_BY (GTK 3's mnemonic labels) is not linted, and a
button that is visible but not showing, as gedit's unrevealed search bar
has, is not linted and not in tree(). No accessibility bus needed. Prints
ok/FAIL lines, like run.sh."""

import sys
import types
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# The module's Unix-only imports, which this test never uses.
for mod in ("fcntl", "grp", "pwd", "termios", "pty", "resource", "tty"):
    sys.modules.setdefault(mod, types.ModuleType(mod))
from shotbox import a11y  # noqa: E402


class Names:
    """An enum whose members are their own names, for AT-SPI's StateType."""

    def __getattr__(self, key):
        return key


ROLES = {name: i for i, name in enumerate(
    ("ENTRY", "BUTTON", "LABEL", "TEXT", "IMAGE", "PUSH_BUTTON"), 1)}
Atspi = types.SimpleNamespace(
    Role=types.SimpleNamespace(**ROLES),
    StateType=Names(),
    RelationType=types.SimpleNamespace(LABELLED_BY="LABELLED_BY"))


class States:
    def __init__(self, names):
        self.names = set(names)

    def contains(self, name):
        return name in self.names


class Relation:
    def __init__(self, kind, targets):
        self.kind, self.targets = kind, targets

    def get_relation_type(self):
        return self.kind

    def get_n_targets(self):
        return len(self.targets)

    def get_target(self, i):
        return self.targets[i]


class Acc:
    app, path = None, ""

    def __init__(self, role, name="", states=(), relations=()):
        self.role, self.name = role, name
        self.states, self.relations = ("VISIBLE", "SHOWING", "SENSITIVE") + tuple(states), relations

    def get_state_set(self):
        return States(self.states)

    def get_name(self):
        return self.name

    def get_description(self):
        return ""

    def get_role(self):
        return ROLES[self.role]

    def get_role_name(self):
        return self.role.lower()

    def get_relation_set(self):
        return self.relations

    def get_child_count(self):
        return 0


def nodes_of(accs):
    return [a11y.node(Atspi, acc, acc.get_state_set(), f"frame/{acc.role.lower()}[{i}]")
            for i, acc in enumerate(accs)]


def lint_of(accs):
    return [what for _, what in a11y.lint(Atspi, nodes_of(accs))]


def tree_of(accs):
    """The paths tree() gives, with walk() standing in for the bus."""
    walked = [(0, n) for n in nodes_of(accs)]
    with mock.patch.object(a11y, "atspi", return_value=Atspi), \
            mock.patch.object(a11y, "walk", return_value=walked):
        return [n.path for n in a11y.tree()]


label = Acc("LABEL", "Text")
# GTK 3: the entry has no name of its own, its mnemonic label is LABELLED_BY it.
entry = Acc("ENTRY", states=("FOCUSABLE", "EDITABLE"),
            relations=[Relation("LABELLED_BY", [label])])
# gedit: an unrevealed search bar's buttons are visible, but not showing.
hidden = Acc("BUTTON", states=("FOCUSABLE",))
hidden.states = tuple(s for s in hidden.states if s != "SHOWING")
hidden_path = "frame/button[2]"

problems = lint_of([label, entry, hidden])
shown = tree_of([label, entry, hidden])
if problems == [] and hidden_path not in shown:
    print("ok: lint() leaves a labelled entry and a node not showing alone, "
          "and tree() leaves the node not showing out")
    sys.exit(0)
print(f"FAIL: lint() gave {problems!r}, expected []; "
      f"tree() gave {shown!r}, expected no {hidden_path!r}")
sys.exit(1)
