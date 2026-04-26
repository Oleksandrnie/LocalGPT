import sys

from backend.apps.tts.providers import piper_provider as _impl

sys.modules[__name__] = _impl
