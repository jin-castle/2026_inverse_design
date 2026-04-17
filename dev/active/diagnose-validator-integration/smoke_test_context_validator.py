import importlib.util
from pathlib import Path

root = Path(__file__).resolve().parents[3]
mod_path = root / 'api' / 'context_validator.py'
spec = importlib.util.spec_from_file_location('context_validator', mod_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

blocked_code = 'resolution = 5\ndpml = 0.3\nsim.run(until=20)\n'
allowed_code = 'resolution = 20\ndpml = 1.0\nsim.run(until=20)\n'

print('BLOCKED', mod.validate_patch_context(blocked_code, {'source': 'test'}))
print('ALLOWED', mod.validate_patch_context(allowed_code, {'source': 'test'}))
