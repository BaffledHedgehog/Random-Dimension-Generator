import difflib, io, sys

BASE = r"C:/Users/yarik_temp/AppData/Roaming/FreesmLauncher/instances/26.2/minecraft/saves/datapuk/datapacks/random_dim"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def show(a, b, head=None, context=2):
    with io.open(f"{BASE}/{a}", encoding="utf-8", errors="replace") as f:
        al = f.readlines()
    with io.open(f"{BASE}/{b}", encoding="utf-8", errors="replace") as f:
        bl = f.readlines()
    d = list(difflib.unified_diff(al, bl, fromfile=a, tofile=b, n=context))
    sys.stdout.write(f"==== {a} vs {b}: {len(d)} diff lines ====\n")
    if head:
        d = d[:head]
    sys.stdout.writelines(d)

if __name__ == "__main__":
    show("generate_dimension.py.bak", "generate_dimension.py", head=None)
