"""Native machine observations and guarded actions, shared by operator transports.

The hub socket remains the single action writer; clients never instantiate an
independent action owner. Persisted wire schemas retain their historical names.
"""

SCHEMA = "sinnix-hub-v1"
