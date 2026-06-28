#!/bin/bash
# Download all male RVC models in parallel from HF mirror
HF="https://hf-mirror.com/chaye741/RVC-Voice-Models/resolve/main"
DEST="/u/projects/Retrieval-based-Voice-Conversion-WebUI/assets/weights"
mkdir -p "$DEST"

# URL-encoded Chinese names
declare -A URLS=(
  # PTH files
  ["nansheng_09.pth"]="$HF/weights/%E7%94%B7%E5%A3%B0-09%E5%8F%B7.pth"
  ["nansheng_10.pth"]="$HF/weights/%E7%94%B7%E5%A3%B0-10%E5%8F%B7.pth"
  ["nansheng_yansang.pth"]="$HF/weights/%E7%94%B7%E5%A3%B0-%E7%83%9F%E5%97%93.pth"
  ["nansheng_nanshen.pth"]="$HF/weights/%E7%94%B7%E5%A3%B0-%E7%94%B7%E7%A5%9E.pth"
  ["nansheng_qingnian.pth"]="$HF/weights/%E7%94%B7%E5%A3%B0-%E9%9D%92%E5%B9%B4.pth"
  ["nansheng_shouruo.pth"]="$HF/weights/%E7%94%B7%E5%A3%B0-%E9%9D%92%E5%B9%B4%E7%98%A6%E5%BC%B1.pth"
  ["dingzhen.pth"]="$HF/weights/%E4%B8%81%E7%9C%9F.pth"
  ["lubenwei.pth"]="$HF/weights/%E5%8D%A2%E6%9C%AC%E4%BC%9F.pth"
  # INDEX files
  ["nansheng_01.index"]="$HF/indices/%E7%94%B7%E5%A3%B0-01%E5%8F%B7.index"
  ["nansheng_02.index"]="$HF/indices/%E7%94%B7%E5%A3%B0-02%E5%8F%B7.index"
  ["nansheng_03.index"]="$HF/indices/%E7%94%B7%E5%A3%B0-03%E5%8F%B7.index"
  ["nansheng_04.index"]="$HF/indices/%E7%94%B7%E5%A3%B0-04%E5%8F%B7.index"
  ["nansheng_06.index"]="$HF/indices/%E7%94%B7%E5%A3%B0-06%E5%8F%B7.index"
  ["nansheng_07.index"]="$HF/indices/%E7%94%B7%E5%A3%B0-07%E5%8F%B7.index"
  ["nansheng_08.index"]="$HF/indices/%E7%94%B7%E5%A3%B0-08%E5%8F%B7.index"
  ["nansheng_09.index"]="$HF/indices/%E7%94%B7%E5%A3%B0-09%E5%8F%B7.index"
  ["nansheng_10.index"]="$HF/indices/%E7%94%B7%E5%A3%B0-10%E5%8F%B7.index"
  ["nansheng_yansang.index"]="$HF/indices/%E7%94%B7%E5%A3%B0-%E7%83%9F%E5%97%93.index"
  ["nansheng_nanshen.index"]="$HF/indices/%E7%94%B7%E5%A3%B0-%E7%94%B7%E7%A5%9E.index"
  ["nansheng_qingnian.index"]="$HF/indices/%E7%94%B7%E5%A3%B0-%E9%9D%92%E5%B9%B4.index"
  ["nansheng_shouruo.index"]="$HF/indices/%E7%94%B7%E5%A3%B0-%E9%9D%92%E5%B9%B4%E7%98%A6%E5%BC%B1.index"
  ["dingzhen.index"]="$HF/indices/%E4%B8%81%E7%9C%9F.index"
  ["lubenwei.index"]="$HF/indices/%E5%8D%A2%E6%9C%AC%E4%BC%9F.index"
)

# Download in parallel (max 5 at a time)
for f in "${!URLS[@]}"; do
  url="${URLS[$f]}"
  dest="$DEST/$f"
  if [ -f "$dest" ]; then
    size=$(stat -c%s "$dest" 2>/dev/null || echo 0)
    if [ "$size" -gt 1000000 ]; then
      echo "[SKIP] $f (exists)"
      continue
    fi
  fi
  echo "[GET] $f"
  curl -L -s -o "$dest" "$url" &
  # Limit concurrency
  while [ $(jobs -r | wc -l) -ge 5 ]; do sleep 1; done
done
wait
echo "All done!"
ls -lh "$DEST"/nansheng_* "$DEST"/dingzhen.* "$DEST"/lubenwei.* 2>/dev/null
