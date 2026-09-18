#!/bin/bash
cd /c/Users/yarik_temp/AppData/Local/Temp/mc262-final
JAVA=/c/Users/yarik_temp/AppData/Roaming/FreesmLauncher/java/java-runtime-epsilon/bin/java.exe
rm -f server.log
(
  until grep -q "Done (" server.log 2>/dev/null; do sleep 0.5; done
  sleep 2
  cat cmds_lazy.txt        # loot spawn / place template / place feature / place structure
  sleep 15
  head -n 8 cmds_force.txt # forceload — генерация чанков в 3 измерениях
  sleep 120                # даём чанкам сгенерироваться (519 placed, карверы, структуры)
  echo stop
) | "$JAVA" -jar server.jar nogui > server.log 2>&1
echo "EXIT=$?"
