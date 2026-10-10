from pathlib import Path
import os, subprocess, sys, tempfile
root=Path(sys.argv[1]).resolve()
out=Path(tempfile.mkdtemp(prefix="at4-check-"))
src=(root/"src/freedreno/vulkan/tu_autotune.cc").read_text()
start=src.index("render_mode get_optimal_mode(\n         rp_history &history")
brace=src.index("{",start);end=brace+1;level=1
while level:
    level+=(src[end]=="{")-(src[end]=="}");end+=1
code=Path(__file__).with_name("at4_selector_wrapper.cpp.in").read_text().replace("METHOD",src[start:end].replace("frane_2633_decision_draw(history.hash)","test_decision_word(history.hash)"))
code=code.replace("LEGACY",Path(__file__).with_name("at3_selector_baseline.cpp.in").read_text().replace("frane_2633_decision_draw(history.hash)","test_decision_word(history.hash)"))
(out/"selector.cpp").write_text(code)
subprocess.run(["g++","-std=c++17","-O1","-g","-fsanitize=address,undefined","-fno-omit-frame-pointer","-I"+str(root/"src/freedreno/vulkan"),str(out/"selector.cpp"),"-o",str(out/"selector")],check=True)
env=dict(os.environ,ASAN_OPTIONS="detect_leaks=0")
subprocess.run([str(out/"selector")],env=env,check=True)
