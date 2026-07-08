import os

os.environ["MYAGV_USE_SIM"] = "1"

from myagv_lab.phase2_nav.nav_node import NavigationManager


nav = NavigationManager()
result = nav.navigate("moon_base")
print(result.success, result.message)
