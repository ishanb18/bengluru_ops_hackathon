import subprocess
with open("old_LiveMap.jsx", "wb") as f:
    out = subprocess.check_output(["git", "show", "HEAD^:frontend/src/components/LiveMap.jsx"])
    f.write(out)
