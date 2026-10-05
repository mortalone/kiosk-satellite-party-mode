"""Validate emitted preset with Music Assistant's pinned primary DSP models."""
import importlib.util
import json
import subprocess
import sys
spec = importlib.util.spec_from_file_location('ma_dsp_models', '/tmp/ma_dsp_models.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
output = subprocess.check_output(['java', '-cp', '/tmp/party-test:/tmp/party-json.jar:/tmp/qr-decoder.jar',
                                  'me.jxl.kiosk.plugins.partymode.PartyEqTest'], text=True)
config = module.DSPConfig.from_dict(json.loads(output.splitlines()[0]))
config.validate()
assert config.enabled and config.input_gain == -5
assert len(config.filters[0].bands) == 4
assert config.filters[0].bands[0].type == module.ParametricEQBandType.LOW_SHELF
assert config.filters[0].bands[0].channel == module.AudioChannel.ALL
print('Party Punch validated by official MA DSP models')
