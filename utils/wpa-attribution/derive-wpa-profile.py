#!/usr/bin/env python3
"""Derive bounded WPAExporter profiles from an installed WPA XML seed."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import uuid
from pathlib import Path

from lxml import etree


def lname(node: etree._Element) -> str:
    return etree.QName(node).localname


def first(parent: etree._Element, name: str) -> etree._Element:
    values = parent.xpath(f'.//*[local-name()="{name}"]')
    if not values:
        raise RuntimeError(f"seed is missing {name}")
    return values[0]


def clone_graph(root: etree._Element, graph_name: str, preset_name: str,
                clsid: str | None = None) -> etree._Element:
    for graph in root.xpath(f'//*[local-name()="{graph_name}"]'):
        if clsid is not None and graph.get("ClsID", "").lower() != clsid.lower():
            continue
        presets = graph.xpath('.//*[local-name()="HdvViewModelPreset"]')
        if presets and presets[0].get("Name") == preset_name:
            return copy.deepcopy(graph)
    raise RuntimeError(f"seed is missing {graph_name}/{preset_name}/{clsid or '*'}")


def replace_preset(graph: etree._Element, replacement: etree._Element) -> None:
    wrapper = next((node for node in graph if lname(node).endswith("HdvViewModelPreset")), None)
    if wrapper is None:
        raise RuntimeError("sampled CPU graph has no preset wrapper")
    wrapper.replace(first(wrapper, "HdvViewModelPreset"), copy.deepcopy(replacement))


def configure_raw(graph: etree._Element, query: str,
                  visible_names: set[str]) -> None:
    preset = first(graph, "HdvViewModelPreset")
    preset.set("InitialFilterQuery", query)
    preset.set("InitialFilterShouldKeep", "True")
    preset.set("InitialSelectionQuery", "")
    preset.set("InitialExpansionQuery", "")
    # Moving WPA's key-column divider to the far left serializes leaf rows.
    preset.set("KeyColumnCount", "0")
    for column in graph.xpath('.//*[local-name()="HdvColumnViewModelPreset"]'):
        if column.get("Name") in visible_names:
            column.set("IsVisible", "True")


def sampled_graph(root: etree._Element, process: str, tid: int | None) -> etree._Element:
    graph = clone_graph(
        root, "CpuSamplingGraphTreeItem",
        "Breakdown by Process, Thread, Activity, Stack",
    )
    presets = root.xpath(
        '//*[local-name()="HdvViewModelPreset" and @Name="Samples by Thread Name"]'
    )
    if not presets:
        raise RuntimeError("seed is missing Samples by Thread Name")
    replace_preset(graph, presets[0])
    for column in list(graph.xpath('.//*[local-name()="HdvColumnViewModelPreset"]')):
        if column.get("Name") == "Thread Activity Tag":
            column.getparent().remove(column)
    query = f'[Process]:="{process}"'
    if tid is not None:
        query += f' [Thread ID]:={tid}'
    configure_raw(
        graph, query,
        {"Process", "Thread Name", "Thread ID", "Stack", "Address", "CPU",
         "TimeStamp", "Weight", "Count", "Thread Start Module",
         "Thread Start Function"},
    )
    return graph


def profile_root(seed_root: etree._Element, graphs: list[etree._Element],
                 titles: list[str]) -> etree._Element:
    root = copy.deepcopy(seed_root)
    for child in list(root):
        if lname(child) in {
            "WpaProfile.UISessions", "WpaProfile.Views",
            "WpaProfile.HdvPresetCollections",
        }:
            root.remove(child)

    session = copy.deepcopy(first(seed_root, "UISessionProperties"))
    for child in list(session):
        if lname(child) == "UISessionProperties.References":
            session.remove(child)
    sessions = etree.Element(
        "{clr-namespace:Microsoft.Performance.Shell;assembly=Microsoft.Performance.Shell}WpaProfile.UISessions"
    )
    sessions.append(session)
    root.append(sessions)

    seed_views = seed_root.xpath('//*[local-name()="AnalysisView"]')
    if len(seed_views) < len(graphs):
        raise RuntimeError("seed has too few serializer-authored AnalysisView identifiers")
    names = [view.get("Name", "") for view in seed_views[:len(graphs)]]
    for name in names:
        uuid.UUID(name)
    base_view = seed_views[0]
    views = etree.Element(
        "{clr-namespace:Microsoft.Performance.Shell;assembly=Microsoft.Performance.Shell}WpaProfile.Views"
    )
    root.append(views)
    for index, (graph, title, name) in enumerate(zip(graphs, titles, names, strict=True)):
        view = copy.deepcopy(base_view)
        for child in list(view):
            if lname(child).endswith("GraphTreeItem"):
                view.remove(child)
        view.set("Name", name)
        view.set("IsSelected", "True" if index == 0 else "False")
        first(view, "ViewTitle").set("Title", title)
        view.append(graph)
        views.append(view)
    return root


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-profile", required=True, type=Path)
    parser.add_argument("--output-profile", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--process-name", required=True)
    parser.add_argument("--pfifo-tid", type=int)
    args = parser.parse_args()

    seed_root = etree.parse(str(args.seed_profile)).getroot()
    process = f"{args.process_name} ({args.pid})"
    cpu = sampled_graph(seed_root, process, args.pfifo_tid)
    graphs = [cpu]
    titles = ["main-vk-pfifo-discovery"]
    if args.pfifo_tid is not None:
        precise = clone_graph(
            seed_root, "CpuSchedulingWithReadyThreadGraphTreeItem", "Thread Delays"
        )
        configure_raw(
            precise,
            f'[New Process]:="{process}" [New Thread Id]:={args.pfifo_tid}',
            {"New Process", "New Thread Id", "Last Switch-Out Time", "Ready Time",
             "Switch-In Time", "Next Switch-Out Time", "Waits", "Ready", "CPU Usage",
             "% CPU Usage", "New Thread Stack", "Ready Thread Stack", "Readying Process",
             "Readying Thread Id", "Cpu", "Count"},
        )
        gpu = clone_graph(
            seed_root, "Core4SummaryTableFillerGraphTreeItem", "GPU by Process",
            "b859d131-dfb5-4605-be19-810b298b6975",
        )
        configure_raw(
            gpu, f'[Process]:="{process}"',
            {"Process Name", "Process", "Type", "ThreadId", "Count", "GPU Time",
             "Initialized", "Submitted To HW", "Start Execution", "Finished", "A/N/E"},
        )
        graphs.extend((precise, gpu))
        titles = ["main-vk-pfifo-sampled", "main-vk-pfifo-precise", "main-vk-gpu"]

    root = profile_root(seed_root, graphs, titles)
    graph_nodes = [node for node in root.iter() if lname(node).endswith("GraphTreeItem")]
    refs = root.xpath(
        '//*[local-name()="ExternalFileReference" or local-name()="FileReference"]'
    )
    presets = [first(node, "HdvViewModelPreset") for node in graph_nodes]
    if len(graph_nodes) != len(graphs) or refs:
        raise RuntimeError("derived-profile graph/reference gate failed")
    if any(node.get("KeyColumnCount") != "0" for node in presets):
        raise RuntimeError("leaf-row gate failed")

    args.output_profile.parent.mkdir(parents=True, exist_ok=True)
    etree.ElementTree(root).write(
        str(args.output_profile), encoding="UTF-8", xml_declaration=True, pretty_print=True
    )
    result = {
        "seed_sha256": sha256(args.seed_profile),
        "output_sha256": sha256(args.output_profile),
        "pid": args.pid,
        "process_name": args.process_name,
        "pfifo_tid": args.pfifo_tid,
        "graph_types": [lname(node) for node in graph_nodes],
        "queries": [node.get("InitialFilterQuery") for node in presets],
        "external_references": len(refs),
        "key_column_counts": [node.get("KeyColumnCount") for node in presets],
    }
    args.manifest.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
