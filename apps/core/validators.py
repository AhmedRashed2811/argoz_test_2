"""Reusable field validators (docs §17). Budget non-negativity is enforced at
field + DB constraint level in marketing; this is the shared field validator."""
from django.core.validators import MinValueValidator

# ponytail: MinValueValidator(0) already does it; alias for intent at call sites.
non_negative = MinValueValidator(0)
