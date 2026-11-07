"""Render the actual GDS, not a conceptual illustration (klayout -b -r)."""
from pathlib import Path
import pya
root = Path(__file__).resolve().parent
out = root / 'results/physical'
view = pya.LayoutView()
view.load_layout(str(out / 'gcd.gds'), False)
view.load_layer_props(str(root / 'orfs/flow/platforms/nangate45/FreePDK45.lyp'))
view.set_config("text-visible", "false")
view.set_config("grid-visible", "false")
view.max_hier()
view.zoom_fit()
view.save_image(str(out / 'gcd-layout.png'), 1200, 1200)
print('LAYOUT_RENDERED')
