"""KLayout adapter: merge the upstream sample DEF with its standard-cell GDS."""
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path
import pya

root = Path(__file__).resolve().parent
out = root / 'results/physical'
platform = root / 'orfs/flow/platforms/nangate45'
# Materialize absolute paths in a derived technology file, leaving upstream intact.
tree = ET.parse(platform / 'FreePDK45.lyt')
tree.find('base-path').text = str(platform)
tree.find('.//lef-files').text = str(root / 'orfs/tools/OpenROAD/test/Nangate45/Nangate45_tech.lef')
ET.SubElement(tree.find('.//lefdef'), 'lef-files').text = str(root / 'orfs/tools/OpenROAD/test/Nangate45/Nangate45_stdcell.lef')
tech = out / 'FreePDK45.absolute.lyt'
tree.write(tech, encoding='utf-8', xml_declaration=True)
spec = importlib.util.spec_from_file_location('def2stream', root / 'orfs/flow/util/def2stream.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
errors = module.merge_gds(pya, str(tech), '', str(out / 'final.def'), 'gcd',
                         str(platform / 'gds/NangateOpenCellLibrary.gds'), '', str(out / 'gcd.gds'))
if errors:
    raise RuntimeError(f'GDS merge reported {errors} errors')
layout = pya.Layout()
layout.read(str(out / 'gcd.gds'))
assert layout.top_cell().name == 'gcd'
assert not layout.top_cell().bbox().empty()
print(f'GDS_PASS top=gcd cells={layout.cells()} bbox={layout.top_cell().bbox()}')
