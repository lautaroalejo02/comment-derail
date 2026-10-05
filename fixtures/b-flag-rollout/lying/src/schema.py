"""Catalog field definitions.

``rollout`` is a fraction of users between 0 and 1 inclusive.
``0.10`` is 10 percent of users.

``mode`` ``off`` disables the flag for every subject, including anyone
on the allow list. A subject on the deny list is off even if they are
also on the allow list. Allow beats the rollout.
"""

ROLLOUT_EXAMPLE_RAW = "0.10"
ROLLOUT_EXAMPLE_PERCENT = 10
