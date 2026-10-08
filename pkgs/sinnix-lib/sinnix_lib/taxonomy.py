"""Collection purpose, independent of ownership and preservation obligations."""

ROLE_VOCABULARY_VERSION = "collection-role-v2"
ROLE_VOCABULARY = {
    "collection": "A mixed collection, including provider-oriented acquisitions.",
    "source": "Acquired or recorded evidence; retain its package and acquisition provenance.",
    "reference": "Material retained for reading, learning, computation or reuse.",
    "notes": "Working observations, concepts, intentions and plans.",
    "workspace": "An owner-managed implementation, research or processing workspace or repository.",
    "state": "Application-native stores, queues and operational state; maintenance belongs to their owner.",
    "history": "Retained past material or recovery collections; restorability is not established by this role.",
    "metadata": "Authored metadata, retained ledgers, receipts and maintenance evidence.",
    "derived-data": "Transformed products, including transcripts, with source lineage and accuracy limits.",
    "media": "Personal photographs, recordings and keepsakes.",
    "creative-work": "Authored or generated creative material.",
    "analysis": "Interpretation and synthesis, distinct from the evidence interpreted.",
    "index": "A retrieval or serving representation, distinct from its source corpus.",
    "navigation": "An entrance or arrangement of links to existing material.",
    "configuration": "Configuration and protected workflow inputs.",
    "backup": "An owner-managed backup repository; this label does not certify current success.",
    "intake": "Material awaiting assignment or disposition, not automatically disposable.",
    "scratch": "Execution scratch; check active references and preservation before cleanup.",
    "unclassified": "Retained material whose purpose is not established sufficiently.",
}

# Decode retained observations; new writes use only the v2 vocabulary.
LEGACY_ROLES = {
    "collection": "collection", "provider-collection": "collection",
    "source-record": "source", "source-export": "source", "capture": "source",
    "source-snapshot": "source", "reference-material": "reference",
    "learning-material": "reference", "dataset": "reference", "model-resource": "reference",
    "working-notes": "notes", "planning": "notes",
    "software-workspace": "workspace", "research-workspace": "workspace",
    "processing-workspace": "workspace", "worktree": "workspace", "git-origin": "workspace",
    "native-store": "state", "runtime-state": "state",
    "history": "history", "recovery": "history",
    "metadata-ledger": "metadata", "maintenance-evidence": "metadata",
    "derived-data": "derived-data", "transcript": "derived-data",
    "personal-media": "media", "creative-work": "creative-work", "analysis": "analysis",
    "index": "index", "navigation": "navigation", "configuration": "configuration",
    "backup-store": "backup", "intake": "intake", "scratch": "scratch",
    "retained-unclassified": "unclassified",
}
