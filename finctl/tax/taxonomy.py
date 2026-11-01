"""Load the management and tax taxonomies from config/taxonomy.yaml.

One file. The dashboard writes its changes there, into the entry they belong to, and the
reasoning for a category stands next to it as a note (`finctl/notizen.py`). Until step 5
the changes went to a second file; `finctl umstellen` merged both.

Both trees are exactly two levels deep. That is a deliberate constraint rather
than an incidental one: deeper trees make rules fiddly to write and reports
awkward to read, and the free-tag axis already absorbs the long tail.

Anlage V positions carry `requires_property`. They are stored once and scoped
by the split's property_id, so a fifth property needs no new categories, and
one object's cost cannot be filed under another object's category.
"""

from __future__ import annotations

import copy
import sqlite3
from pathlib import Path

import yaml

from finctl import notizen as _notizen
from finctl.dateien import yaml_lesen, yaml_schreiben
from finctl.pfade import CONFIG_DIR

TAXONOMY_PATH = CONFIG_DIR / "taxonomy.yaml"
MIGRATIONS_PATH = CONFIG_DIR / "taxonomy_migrations.yaml"


def apply_migrations(conn: sqlite3.Connection,
                     path: Path = MIGRATIONS_PATH) -> dict[str, int]:
    """Move splits off retired categories before the tree is reloaded.

    Renaming or removing a category without this orphans its splits: they keep
    their amount in the ledger but disappear from every report that joins on
    the category, so totals silently stop adding up.
    """
    if not path.exists():
        return {}
    spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    moved: dict[str, int] = {}

    remap = _notizen.ohne(spec.get("remap"))
    for old, new in remap.items():
        cur = conn.execute(
            "UPDATE splits SET mgmt_category_id = ? WHERE mgmt_category_id = ?",
            (new, old))
        if cur.rowcount:
            moved[f"{old} -> {new}"] = cur.rowcount
        conn.execute("UPDATE mgmt_categories SET active = 0 WHERE id = ?", (old,))

    # A category id lives in three places, and migrating only the database
    # leaves the other two to undo it: the rulebook (warned about when
    # retiring) and the saved manual overrides, which are replayed AFTER
    # categorize and therefore put the retired id straight back.
    moved_overrides = remap_overrides(remap)
    if moved_overrides:
        moved["manual overrides"] = moved_overrides

    for dead in (spec.get("retire") or []):
        left = conn.execute(
            "SELECT COUNT(*) FROM splits WHERE mgmt_category_id = ?", (dead,)
        ).fetchone()[0]
        if left:
            raise ValueError(
                f"refusing to retire {dead}: {left} splits still point at it")
        conn.execute("UPDATE mgmt_categories SET active = 0 WHERE id = ?", (dead,))

    conn.commit()
    return moved


def remap_overrides(remap: dict[str, str],
                     path: Path | None = None) -> int:
    """Repoint saved manual decisions at renamed categories."""
    from finctl.rules.categorize import overrides_pfad

    path = path or overrides_pfad()
    if not path.exists() or not remap:
        return 0
    text = path.read_text(encoding="utf-8")
    spec = yaml.safe_load(text) or {}
    entries = spec.get("overrides", []) or []
    changed = 0
    for entry in entries:
        for part in entry.get("parts") or []:
            if part.get("mgmt") in remap:
                part["mgmt"] = remap[part["mgmt"]]
                changed += 1
    if changed:
        header = text.split("overrides:")[0]
        path.write_text(header + yaml.safe_dump({"overrides": entries},
                                                allow_unicode=True, sort_keys=False),
                        encoding="utf-8")
    return changed


def deactivate_missing(conn: sqlite3.Connection, path: Path = TAXONOMY_PATH) -> int:
    """Hide categories no longer declared, without deleting history."""
    spec = load_spec(path)
    declared = set()
    for parent, node in (spec.get("management") or {}).items():
        declared.add(parent)
        declared.update(f"{parent}/{leaf}" for leaf in (node.get("children") or {}))
    rows = conn.execute("SELECT id FROM mgmt_categories WHERE active = 1").fetchall()
    n = 0
    for row in rows:
        if row["id"] not in declared:
            conn.execute("UPDATE mgmt_categories SET active = 0 WHERE id = ?", (row["id"],))
            n += 1
    conn.commit()
    return n


def _ohne_notizen(spec: dict) -> dict:
    """Die Blaetter sind die Kategorien: ein Schluessel `notiz` waere eine."""
    for achse in ("management", "tax"):
        for node in (spec.get(achse) or {}).values():
            if isinstance(node, dict) and isinstance(node.get("children"), dict):
                node["children"] = _notizen.ohne(node["children"])
    return spec


def aus_spec(spec: dict) -> dict:
    """A loaded taxonomy as the loader sees it: leaves without notes."""
    return _ohne_notizen(copy.deepcopy(spec or {}))


def load_spec(path: Path = TAXONOMY_PATH) -> dict:
    return aus_spec(yaml_lesen(path))


def save(axis: str, parent: str, leaf: str, label, *,
         remove: bool = False, path: Path = TAXONOMY_PATH) -> None:
    """Record a dashboard category change in taxonomy.yaml, in the entry it belongs to.

    A leaf that has more than a name (`{name: ..., tax: ..., fix: true}`) keeps the rest
    when it is renamed. A parent with a note stays, with or without leaves.
    """
    for name in (parent, leaf):
        _notizen.kennung_pruefen(name, "Kategorie")
    spec = (yaml_lesen(path) or {}) if path.exists() else {}
    baum = spec.setdefault(axis, {})
    node = baum.get(parent)
    if node is None:
        if remove:
            return
        node = baum[parent] = {"name": parent, "kind": "expense", "children": {}}
    children = node.get("children")
    if not isinstance(children, dict):
        children = node["children"] = {}
    if remove:
        children.pop(leaf, None)
    elif isinstance(children.get(leaf), dict):
        children[leaf] = {**children[leaf], "name": label}
    else:
        children[leaf] = label
    yaml_schreiben(path, spec)


def add_migration(old: str, new: str, path: Path = MIGRATIONS_PATH) -> None:
    """Record where a retired category's splits should move."""
    spec = {}
    if path.exists():
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    header = ""
    if path.exists():
        text = path.read_text(encoding="utf-8")
        header = text.split("remap:")[0] if "remap:" in text else ""
    spec.setdefault("remap", {})[old] = new
    spec.setdefault("retire", [])
    path.write_text(header + yaml.safe_dump(
        {"remap": spec["remap"], "retire": spec["retire"]},
        allow_unicode=True, sort_keys=False), encoding="utf-8")


def rules_referencing(category_id: str, path: Path | None = None) -> list[str]:
    """Rules pointing at a category.

    Retiring a category without moving its rules is the mistake that bit us
    once already: the splits migrate, then the next categorize puts them
    straight back through a rule still naming the old id.

    Reads rules.yaml, which /regeln writes whole, and the shipped general rules
    where the layer is switched on.
    """
    from finctl.rules.engine import rohe_regeln

    try:
        eintraege = rohe_regeln(path)
    except FileNotFoundError:
        return []
    hits = []
    for rule in eintraege:
        blob = yaml.safe_dump(rule.get("set", {}) or {})
        if category_id in blob:
            hits.append(rule.get("id", "?"))
    return hits


def kennungen_pruefen(spec: dict) -> None:
    """Jede Kategorie-Kennung ist klein geschrieben, sonst wird nichts geladen.

    Vergleiche auf Kennungen laufen an zwei Stellen: in SQL (`LIKE`, fuer ASCII
    ohne Unterschied zwischen Gross und Klein) und in Python (`startswith`, mit
    Unterschied). Die Oberflaeche legt Kennungen klein an, eine von Hand
    geschriebene taxonomy.yaml nicht zwingend. Statt jeden Vergleich einzeln
    abzusichern, gibt es hier nur noch kleine Kennungen -- danach ist jeder
    Praefixvergleich in Python so sicher wie der in SQL, auch die kuenftigen.
    """
    falsche = []
    for parent, node in (spec.get("management") or {}).items():
        falsche += [kennung for kennung in
                    (parent, *(f"{parent}/{leaf}" for leaf in (node.get("children") or {})))
                    if kennung != kennung.lower()]
    if falsche:
        raise ValueError(
            "Kategorie-Kennungen mit Großbuchstaben: " + ", ".join(falsche)
            + ". Kennungen sind klein geschrieben; der Anzeigename darf Großbuchstaben haben.")


def load_into_db(conn: sqlite3.Connection, path: Path = TAXONOMY_PATH) -> dict[str, int]:
    spec = load_spec(path)
    kennungen_pruefen(spec)
    counts = {"mgmt": 0, "tax": 0}

    for order, (parent_id, node) in enumerate(spec.get("management", {}).items()):
        kind = node.get("kind", "expense")
        # A parent may declare `fix: true` for all its children -- every
        # insurance and every subscription is a fixed cost, and repeating the
        # flag on each one would just be noise to keep in sync.
        parent_fix = bool(node.get("fix", False))
        # `einmalig: true` works like `fix: true`: on the parent for every child,
        # on a child for itself. What is booked there does not come back.
        parent_einmalig = bool(node.get("einmalig", False))
        conn.execute(
            """
            INSERT INTO mgmt_categories (id, parent_id, name, kind, sort_order,
                                         fixkosten, einmalig, active)
            VALUES (?, NULL, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name, kind = excluded.kind,
                sort_order = excluded.sort_order,
                fixkosten = excluded.fixkosten,
                einmalig = excluded.einmalig,
                -- Re-declaring revives: without this a category that was once
                -- retired stays dead forever, and any split migrated into it is
                -- silently orphaned.
                active = 1
            """,
            (parent_id, node["name"], kind, order, int(parent_fix),
             int(parent_einmalig)),
        )
        counts["mgmt"] += 1
        for child_order, (leaf, value) in enumerate(node.get("children", {}).items()):
            # A child is either a plain label or a mapping that also declares
            # the tax position the category implies and whether it is fixed.
            if isinstance(value, dict):
                label, default_tax = value.get("name", leaf), value.get("tax")
                fix = bool(value.get("fix", parent_fix))
                einmalig = bool(value.get("einmalig", parent_einmalig))
            else:
                label, default_tax, fix = value, None, parent_fix
                einmalig = parent_einmalig
            conn.execute(
                """
                INSERT INTO mgmt_categories (id, parent_id, name, kind, sort_order,
                                             default_tax_id, fixkosten, einmalig, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name, parent_id = excluded.parent_id,
                    kind = excluded.kind, sort_order = excluded.sort_order,
                    default_tax_id = excluded.default_tax_id,
                    fixkosten = excluded.fixkosten,
                    einmalig = excluded.einmalig,
                    active = 1
                """,
                (f"{parent_id}/{leaf}", parent_id, label, kind, child_order,
                 default_tax, int(fix), int(einmalig)),
            )
            counts["mgmt"] += 1

    for order, (parent_id, node) in enumerate(spec.get("tax", {}).items()):
        anlage = node.get("anlage")
        conn.execute(
            """
            INSERT INTO tax_categories
                (id, parent_id, name, anlage, deductible, requires_property, sort_order, active)
            VALUES (?, NULL, ?, ?, 0, 0, ?, 1)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name, anlage = excluded.anlage,
                sort_order = excluded.sort_order, active = 1
            """,
            (parent_id, node["name"], anlage, order),
        )
        counts["tax"] += 1
        for child_order, (leaf, meta) in enumerate(node.get("children", {}).items()):
            conn.execute(
                """
                INSERT INTO tax_categories
                    (id, parent_id, name, anlage, deductible, requires_property,
                     sort_order, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name, parent_id = excluded.parent_id,
                    anlage = excluded.anlage, deductible = excluded.deductible,
                    requires_property = excluded.requires_property,
                    sort_order = excluded.sort_order, active = 1
                """,
                (
                    f"{parent_id}/{leaf}", parent_id, meta["name"], anlage,
                    int(bool(meta.get("deductible", False))),
                    int(bool(meta.get("property", False))),
                    child_order,
                ),
            )
            counts["tax"] += 1

    conn.commit()
    return counts


def display_name(
    conn: sqlite3.Connection, tax_category_id: str, property_id: str | None
) -> str:
    """Render a tax position the way it should read in a report.

    Property-scoped positions come out as "<Objekt> - Erhaltungsaufwendungen";
    everything else keeps its own name.
    """
    row = conn.execute(
        "SELECT name, requires_property FROM tax_categories WHERE id = ?",
        (tax_category_id,),
    ).fetchone()
    if row is None:
        return tax_category_id
    if not row["requires_property"] or not property_id:
        return row["name"]
    prop = conn.execute(
        "SELECT name FROM properties WHERE id = ?", (property_id,)
    ).fetchone()
    label = prop["name"] if prop else property_id
    return f"{label} - {row['name']}"
