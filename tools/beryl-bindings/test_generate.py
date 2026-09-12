#!/usr/bin/env python3
"""Analytical extraction and provenance failures; no engine execution."""
import copy
import json
from pathlib import Path
import unittest
import generate


class ExtractionTests(unittest.TestCase):
    def document(self, name="Read", signature="proto int", suffix=" (int n=0)"):
        return ('<meta name="generator" content="Doxygen 1.16.1"/>\n'
                '<p>UTF-8: \u03bb</p>\n'
                f'<tr class="memitem:a1" id="r_a1"><td class="memItemLeft">{signature}&#160;</td>'
                f'<td class="memItemRight"><a class="el" href="#a1">{name}</a>{suffix}</td></tr>').encode()

    def test_exact_unicode_origin_and_declaration(self):
        data = self.document()
        row, = generate.extract(data, "Array", "api.html", ["Read"])
        self.assertEqual(row["signature"], "proto int Read (int n=0)")
        self.assertEqual(row["source"]["line"], 3)
        origin = row["source"]
        fragment = data[origin["byte_offset"]:origin["byte_offset"] + origin["byte_length"]]
        self.assertEqual(origin["fragment_sha256"], generate.digest(fragment))
        self.assertTrue(fragment.startswith(b'<tr class="memitem:'))

    def test_template_reference_and_default_preserved(self):
        row, = generate.extract(self.document(signature="ref array&lt; <a>float</a> &gt;", suffix=" = 0"), "X", "api.html", ["Read"])
        self.assertEqual(row["signature"], "ref array< float > Read = 0")
        self.assertEqual(row["kind"], "field")

    def test_missing_duplicate_and_old_layout_rejected(self):
        for data in (self.document("Other"), self.document() + self.document(),
                     self.document().replace(b"Doxygen 1.16.1", b"Doxygen 1.15.0")):
            with self.assertRaises(ValueError):
                generate.extract(data, "X", "api.html", ["Read"])

    def test_inherited_member_is_not_claimed_as_local(self):
        data = self.document().replace(b'href="#a1"', b'href="interfaceParent.html#a1"')
        with self.assertRaises(ValueError):
            generate.extract(data, "X", "api.html", ["Read"])

    def test_executable_markup_rejected(self):
        with self.assertRaises(ValueError):
            generate.extract(self.document(signature="<script>x()</script>int"), "X", "api.html", ["Read"])

    def test_input_bounds_and_unicode_rejected(self):
        for data in (b"", b"\xff", b"x" * (8 * 1024 * 1024 + 1)):
            with self.assertRaises((ValueError, UnicodeError)):
                generate.extract(data, "X", "api.html", ["Read"])

    def test_snapshot_and_generated_bytes_match(self):
        snapshot = json.loads(generate.SNAPSHOT.read_text(encoding="utf-8"))
        self.assertEqual(generate.GENERATED.read_bytes(), generate.render(snapshot).encode())
        self.assertEqual(snapshot["extractor_sha256"], generate.digest(Path(generate.__file__).read_bytes()))

    def test_snapshot_mutations_rejected(self):
        original = json.loads(generate.SNAPSHOT.read_text(encoding="utf-8"))
        mutations = [lambda x: x.update(extra=True),
                     lambda x: x["declarations"].append(x["declarations"][0]),
                     lambda x: x["declarations"][0]["source"].update(document="../outside.html"),
                     lambda x: x["declarations"][0]["source"].update(byte_length=True),
                     lambda x: x["declarations"][0]["source"].update(fragment_sha256="bad"),
                     lambda x: next(row for row in x["declarations"] if row["owner"] == "array")["source"].update(document_sha256="0" * 64),
                     lambda x: x["engine"].update(bytes=-1),
                     lambda x: x["declarations"].reverse()]
        for mutate in mutations:
            current = copy.deepcopy(original)
            mutate(current)
            with self.assertRaises(ValueError):
                generate.render(current)


if __name__ == "__main__":
    unittest.main()
