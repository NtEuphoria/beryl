"""Bounded construction comparison against preserved MESH terrain source.

This is a semantic prototype. No timing, live height sampling, Canvas publication,
bitwise-float equivalence, or whole-render performance claim is advertised.
"""
import math
import re
import struct

CASES = {
    "flat_water": (0, 1920, 1080),
    "flat_land": (1, 3440, 1440),
    "sea_threshold_checker": (2, 2, 2),
    "row_column_ramp": (3, 1919, 1079),
    "mixed_integer_seed": (4, 3440, 1440),
    "narrow_height_range": (5, 4095, 2047),
}
FLOAT_ROW = "float-equality|engine-operator|adjacent-one-distinct|adjacent-large-distinct|signed-zero-equal"
SCOPE = "Relief command construction before Canvas publication; no sampling, other render layers, pooling, timing, or bitwise-float claim"


def registry():
    return {"name": "compare.terrain.chunks", "implementation": "implemented",
            "runtime_status": "requires execution for the selected engine/artifact",
            "grid": {"width": 80, "height": 80, "samples": 6400},
            "case_ids": list(CASES), "case_selection": "nonempty unique ordered subset; default all",
            "count_parameter": "not admitted; fixed complete cached sample grid",
            "evidence_scope": SCOPE}


def parameters(api, args):
    if args.stage or args.scenario_count is not None:
        raise api.Failure("Terrain comparison uses fixed datasets; --stage/--scenario-count are not admitted")
    selected = args.scenario_case if args.scenario_case is not None else list(CASES)
    if not selected or len(selected) != len(set(selected)) or any(name not in CASES for name in selected):
        raise api.Failure("Terrain cases must be a nonempty unique subset of " + ", ".join(CASES))
    return {"grid": 80, "case_ids": selected}


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def heights(mode):
    out = []
    for row in range(80):
        for col in range(80):
            value = (0.5, 25.0, float((row + col) % 2),
                     row * 2.0 + col * 0.125 - 4.0,
                     ((row * 4093 + col * 7919 + row * col * 17) % 8192 - 1024) * 0.03125,
                     4.0 + row * 0.000244140625)[mode]
            out.append(f32(value))
    return out


def colour(band):
    values = (0xFF2E3B2C, 0xFF364532, 0xFF3F4F39, 0xFF4A5941, 0xFF56634A, 0xFF646E55, 0xFF767D63, 0xFF1B3A48)
    value = values[band]
    channels = []
    for shift in (16, 8, 0):
        channel = (value >> shift) & 255
        linear = f32(math.pow(f32(channel / 255.0), f32(2.2)))
        channels.append(int(max(0.0, min(255.0, f32(linear * 255.0)))))
    result = 0xFF000000 | channels[0] << 16 | channels[1] << 8 | channels[2]
    return result - 2**32


def dataset(api, name):
    mode, width, height = CASES[name]
    values = heights(mode)
    low, high = min(values), max(values)
    span = max(1.0, f32(high - low))
    counts = [0] * 8
    checksum = 0
    for value in values:
        checksum = (checksum * 31 + int(value * 4096) % 1000003) % 1000003
    for row in range(79):
        for col in range(79):
            at = row * 80 + col
            average = f32(f32(f32(f32(values[at] + values[at + 1]) + values[at + 80]) + values[at + 81]) * 0.25)
            band = 7
            if average > 0.5:
                t = f32(f32(average - low) / span)
                band = int(max(0.0, min(6.0, f32(t * 7))))
            counts[band] += 1
    chunks = [(band, min(240, count - start)) for band, count in enumerate(counts) for start in range(0, count, 240)]
    return {"id": name, "generator": mode, "pane": [width, height], "samples": 6400,
            "sample_order": "row * 80 + column, existing cached lattice",
            "python_f32_dataset_sha256": api.digest(struct.pack("<6400f", *values)),
            "engine_fixture_checksum": checksum, "height_range": [low, high], "band_quads": counts,
            "chunks": chunks, "quads": 6241, "triangles": 12482, "vertex_floats": 49928, "indices": 37446}


def expected(api, params):
    rows = [FLOAT_ROW]
    checks = 3
    for name in params["case_ids"]:
        data = dataset(api, name)
        width, height = data["pane"]
        rows.append(f"case|{name}|6400|{data['engine_fixture_checksum']}|{width}|{height}")
        for index, (band, quads) in enumerate(data["chunks"]):
            rows.append(f"chunk|{name}|{index}|{band}|{quads}|{colour(band)}|{quads * 8}|{quads * 6}")
        rows.append(f"end|{name}|{len(data['chunks'])}|6241|12482|49928|37446")
        # Complete vertices, compared indices and independent winding indices;
        # seven command-field checks plus four case checks. No absent runs pass.
        checks += 4 + 7 * len(data["chunks"]) + 49928 + 2 * 37446
    return rows, checks


def sources(api, class_name, token, params):
    provenance = api.parse(api.read(api.HERE / "terrain-reference.json"))
    reference = api.read(api.HERE / "terrain-reference.c.txt")
    if api.digest(reference) != provenance["sha256"]:
        raise api.Failure("Preserved terrain reference does not match its provenance", "stale_input")
    original = reference.decode("utf-8-sig")
    if len(re.findall(r"\bSPK_TerrainMap\b", original)) != 2:
        raise api.Failure("Reference class/constructor identity changed")
    reference_source = re.sub(r"\bSPK_TerrainMap\b", class_name + "Reference", original)
    adapter = api.read(api.HERE / "terrain-adapter.c.in").decode("utf-8").replace("@CLASS@", class_name)
    calls = []
    data = [dataset(api, name) for name in params["case_ids"]]
    for index, item in enumerate(data):
        bands = ", ".join(str(band) for band, _ in item["chunks"])
        width, height = item["pane"]
        calls.append(f'array<int> expectedBands{index} = {{{bands}}};')
        calls.append(f'if (!RunCase("{item["id"]}", {item["generator"]}, {width}, {height}, expectedBands{index})) return m_Result;')
    handler = api.read(api.HERE / "terrain-handler.c.in").decode("utf-8")
    handler = handler.replace("@CLASS@", class_name).replace("@TOKEN@", token).replace("@RUN@", "\n".join(calls))
    return {"scripts/Game/BerylScenario/" + class_name + "Reference.c": reference_source,
            "scripts/Game/BerylScenario/" + class_name + "Adapter.c": adapter,
            "scripts/WorkbenchGameCommon/" + class_name + ".c": handler}, {"reference": provenance, "datasets": data,
            "source_templates": {name: api.digest(api.read(api.HERE / name)) for name in ("terrain-reference.c.txt", "terrain-adapter.c.in")},
            "candidate_revision": "direct-v2-once-per-populated-band-palette; v1 retained in terrain-adapter-v1.c.txt",
            "scope": SCOPE, "float_comparison": "engine == operator; adjacent values probed; signed zero not distinguished; no bit encoding verified"}


def validate_response(api, response, token, params):
    import scenarios
    wanted, checks = expected(api, params)
    rows, checksum = scenarios.validate_wire(api, response, token, params["case_ids"], checks, len(wanted))
    if rows != wanted:
        first = next((i for i, pair in enumerate(zip(rows, wanted)) if pair[0] != pair[1]), 0)
        raise api.Failure(f"Terrain trace differs from the independent dataset/command fixture at row {first}")
    trace = ("\n".join(rows) + "\n").encode("ascii")
    return trace, {"checks": checks, "events": len(rows), "case_ids": params["case_ids"], "checksum": checksum,
                   "checksum_algorithm": "polynomial31_mod1000003_ascii_lf", "sha256": api.digest(trace),
                   "float_comparison": "engine == operator on all vertex and UV values; adjacent probes pass; no bitwise or signed-zero distinction",
                   "payload_scope": "TriMeshDrawCommand m_iColor, m_Vertices, m_Indices, m_fUVScale, m_pTexture; command sequence and independent quad winding",
                   "scope": SCOPE}
