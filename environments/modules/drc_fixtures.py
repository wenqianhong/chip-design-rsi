"""Run with klayout -b -r: engineering fixtures, not a chip benchmark."""
import pya
from pathlib import Path

out = Path(__file__).resolve().parent / "results"
out.mkdir(exist_ok=True)
for name, width in [("metal_good", 100), ("metal_bad", 30)]:
    layout = pya.Layout()
    layout.dbu = 0.001  # micrometers: one database unit = 1 nm
    cell = layout.create_cell("fixture")
    cell.shapes(layout.layer(11, 0)).insert(pya.Box(0, 0, 1000, width))
    layout.write(str(out / (name + ".gds")))
    print(f"{name}: metal1 width={width} nm, length=1000 nm")
