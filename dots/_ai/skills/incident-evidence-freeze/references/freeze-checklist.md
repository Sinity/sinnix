# Freeze checklist

The evidence directory must contain:

- manifest.json with UTC timestamp, repository root, branch, HEAD, and
  relative artifact paths.
- status.txt, reflog.txt, diff.patch, and cached.patch.
- conflicts/ copies of only the explicitly named files, with SHA-256 hashes
  in the manifest.

The freeze authorizes no repair. A separate operator decision must name the
exact file, ref, Beads record, service, or snapshot to mutate. Verify the
mutation against the frozen hash or state transition, then append the result
to the incident record.
