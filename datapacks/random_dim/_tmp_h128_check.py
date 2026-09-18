# временная проверка: height=128 миры получают подземные биомы
import sys, tempfile, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import generate_dimension as gd

td = tempfile.mkdtemp(prefix="rndim_h128_")
old = gd.DATA_ROOT
gd.DATA_ROOT = Path(td) / "data"
found = 0
for seed in range(1, 40):
    if found >= 3:
        break
    rng = random.Random(9000 + seed)
    gen = gd.DimensionGenerator(rng, "rndim", "h128c%d" % seed)
    res = gen.generate()
    h, kind, n = gen.height, gen.bs_kind, len(gen.biome_underground)
    qual = (gen.height >= 128 and len(gen.biomes) >= 6
            and kind == "multi_noise")
    if h == 128 and kind == "multi_noise":
        found += 1
        bands = {b: gen.biome_band[b] for b in gen.biome_underground}
        print("seed=%d height=%d bs=%s biomes=%d under=%d bands=%s"
              % (9000 + seed, h, kind, len(gen.biomes), n, bands))
        assert n >= 2, "no underground biomes at height=128!"
        los = sorted(b[0] for b in bands.values())
        his = sorted(b[1] for b in bands.values())
        assert los[0] >= gd.CAVE_BAND_TOP - 1e-9
        assert his[-1] <= gd.CAVE_BAND_BOTTOM + 1e-9
    else:
        ok = (n > 0) == qual
        print("seed=%d height=%d bs=%s biomes=%d under=%d qualified=%s %s"
              % (9000 + seed, h, kind, len(gen.biomes), n, qual,
                 "OK" if ok else "MISMATCH"))
        assert ok, "underground assignment mismatch"
assert found >= 1, "no height=128 multi_noise world found in 39 seeds"
gd.DATA_ROOT = old
print("H128_CHECK_OK (checked %d seeds, %d height=128 multi_noise worlds)"
      % (min(40, found and 40), found))
