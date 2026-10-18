# Retrieve native file references

Use this route when requested files belong to older, unrendered turns, or when
rendered controls cannot distinguish versions. Read `full` first and select
file references from its native messages. Search locally with `locate` before
downloading inputs. A local copy needs identity evidence such as the native
filename and byte count; a similarly named newer export is insufficient.

Write an explicit request array in a private scratch directory:

```json
[
  {"kind": "link", "name": "report.zip", "message_id": "native-message-id", "sandbox_path": "/mnt/data/report.zip"},
  {"kind": "upload", "name": "input.zip", "file_id": "file_native_id", "expected_bytes": 1234}
]
```

Generated links use the containing message's provider ID and the sandbox path
from its text. Remove the `sandbox:` prefix and any fragment. Uploads use
`metadata.attachments[].id`, `name`, and `size` as `expected_bytes`. Destination
names must be unique basenames. Include only the files the operator requested.

```bash
scripts/sinnix-chatgpt-conversations download-native PAGE_ID REQUESTS_JSON DESTINATION
```

The helper retrieves file metadata in the selected authenticated page, starts
a browser download, and copies only a newly completed requested or provider
filename, including numbered Chrome collision variants, into `DESTINATION`.
The provider's Content-Disposition may override the requested name.
Authentication tokens and signed URLs
stay inside the page. It does not navigate or send messages. The destination
receipt has mode 600 and records source reference, path, byte count, SHA-256,
and per-file status. Existing receipts and destination files are refused.

The default completion limit is 120 seconds. Set
`SINNIX_CHATGPT_DOWNLOAD_TIMEOUT_SEC=600` for a known large archive. Timeout
does not cancel Chrome's transfer; inspect Downloads before retrying. A native
byte-count mismatch is a failure even if Chrome has renamed the file. Check
archive integrity before accepting it. Do not conceal a partial transfer as a
complete attachment.

For an explicitly requested full archive, preserve native records and collect
both assistant sandbox links and user attachment references. A retained bundle
may supply the linked individual members. Build a manifest mapping every link,
including repeated occurrences and fragments, to a local file or an explicit
unavailable status. Keep each version separate. Unpack archives without path
traversal or symlink escapes, and do not execute their contents.
