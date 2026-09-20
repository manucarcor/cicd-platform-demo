#!/usr/bin/env python3
"""Simple JUnit XML parser that prints total/passed/failed/skipped counts as JSON."""
import sys
import xml.etree.ElementTree as ET
import json


def parse(path):
    tree = ET.parse(path)
    root = tree.getroot()
    total = 0
    failures = 0
    errors = 0
    skipped = 0
    # JUnit can be <testsuites> or <testsuite>
    suites = []
    if root.tag == 'testsuites':
        suites = list(root.findall('testsuite'))
    elif root.tag == 'testsuite':
        suites = [root]

    for s in suites:
        total += int(s.attrib.get('tests', 0))
        failures += int(s.attrib.get('failures', 0))
        errors += int(s.attrib.get('errors', 0))
        skipped += int(s.attrib.get('skipped', 0))

    passed = total - failures - errors - skipped
    return {
        'total': total,
        'passed': passed,
        'failures': failures,
        'errors': errors,
        'skipped': skipped,
    }


def main():
    if len(sys.argv) < 2:
        print('usage: parse_junit.py <junit-xml-path>', file=sys.stderr)
        sys.exit(2)
    path = sys.argv[1]
    stats = parse(path)
    print(json.dumps(stats))


if __name__ == '__main__':
    main()
