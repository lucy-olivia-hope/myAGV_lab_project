# Day 2 - Navigation (Nav2 + AMCL)

## Objective

Localize the robot on the Day 1 map, then navigate autonomously to goals using Nav2 and AMCL.

## The two order rules

These are the two rules that prevent the lifecycle bugs we hit:

1. Set `/map_server yaml_filename` before configuring `/map_server`.
2. Publish the initial pose only after `/amcl` is active.

If `map_server configure` fails once because `yaml_filename` was missing, restart Nav2 and redo the order from the beginning. Later `param set` commands will not rescue that failed bringup.

## Before you start

- Put the robot on the floor, roughly where it was when the Day 1 map was built.
- Know the full path to your Day 1 map YAML, for example:

```bash
/ws/src/myAGV_lab_project/maps/lab_map.yaml
```

- Make sure the map YAML `image:` line points to the PGM file, usually:

```yaml
image: lab_map.pgm
```

## After pulling the repo on the robot

Inside the robot container:

```bash
cd /ws/src/myAGV_lab_project
git pull origin main
cd /ws
colcon build --packages-select myagv_lab
source /ws/install/setup.bash
```

If your branch is `master`, use:

```bash
git pull origin master
```

Copy or confirm your Day 1 map is in the repo:

```bash
ls /ws/src/myAGV_lab_project/maps
cat /ws/src/myAGV_lab_project/maps/lab_map.yaml
```

You should see `lab_map.yaml` and `lab_map.pgm`.

## 1. Connect and enter the container

From your laptop:

```bash
ssh ubuntu@<robot-IP>
```

On the robot:

```bash
sudo docker start myagv_slam
sudo docker exec -it myagv_slam bash
source /opt/ros/galactic/setup.bash
source /ws/install/setup.bash
```

Repeat the two `source` lines in every new container terminal.

## 2. Start the base (Window 1)

```bash
ros2 launch myagv_odometry myagv_active.launch.py
```

Expected: steady output, with no repeating `Serial port verification failed`.

## 3. Start Nav2 (Window 2)

Open a new terminal, enter the container, source ROS and the workspace, then:

```bash
ros2 launch myagv_lab nav2_launch.py
```

Expected: Nav2 nodes start but wait for lifecycle activation. You may see transform messages like `map does not exist`; that is normal until the map server and AMCL are active and the initial pose has been sent.

## 4. Activate map_server and amcl (Window 3)

Open a new terminal, enter the container, source ROS and the workspace.

Set the map path first. Use your actual map YAML path:

```bash
ros2 param set /map_server yaml_filename /ws/src/myAGV_lab_project/maps/lab_map.yaml
```

Now configure and activate the lifecycle nodes:

```bash
ros2 lifecycle set /map_server configure
ros2 lifecycle set /map_server activate
ros2 lifecycle set /amcl configure
ros2 lifecycle set /amcl activate
```

Check both are active:

```bash
ros2 lifecycle get /map_server
ros2 lifecycle get /amcl
```

Both should say `active`.

If `map_server configure` prints `Transitioning failed` or says `yaml_filename` is not initialized, stop Nav2 in Window 2 with `Ctrl+C`, restart it, then redo this step with the `param set` command first.

## 5. Publish the initial pose

Only do this after `/amcl` is active.

If the robot is near the map origin/start point, use:

```bash
ros2 topic pub -1 /initialpose geometry_msgs/msg/PoseWithCovarianceStamped "{header: {frame_id: 'map'}, pose: {pose: {position: {x: 0.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}}}"
```

If the robot is not at the map origin, set the pose from RViz2 with **2D Pose Estimate** instead.

Expected: the repeating `map does not exist` messages stop within a second or two because AMCL starts publishing `map -> odom`.

If you see an extrapolation error, raise AMCL's transform tolerance and send the initial pose again:

```bash
ros2 param set /amcl transform_tolerance 1.0
```

## 6. Confirm localization converged

```bash
ros2 run tf2_ros tf2_echo map odom
```

Expected: Translation and rotation values are stable each second. If they jump by metres, the initial pose is wrong; publish it again more accurately.

## 7. Send a goal

Pick a free space inside the map. This goal is an absolute map coordinate:

```bash
ros2 topic pub -1 /goal_pose geometry_msgs/msg/PoseStamped "{header: {frame_id: 'map'}, pose: {position: {x: 0.5, y: 0.0, z: 0.0}, orientation: {w: 1.0}}}"
```

Expected: Nav2 receives the goal, plans a path, publishes `/cmd_vel`, and the robot moves.

If the robot does not move, test the base directly:

```bash
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.1}, angular: {z: 0.0}}"
```

- If it moves, the base is fine and the issue is upstream: localization, map, goal, or Nav2.
- If it does not move, check the base launch and the `/cmd_vel` topic.

## Optional: RViz2

From your laptop:

```bash
ssh -X ubuntu@<robot-IP>
xhost +
sudo docker exec -it -e DISPLAY=$DISPLAY myagv_slam bash
source /opt/ros/galactic/setup.bash
source /ws/install/setup.bash
rviz2
```

In RViz2:

- Set **Fixed Frame** to `map`.
- Add `/map`, `/scan`, and TF.
- Use **2D Pose Estimate** only after AMCL is active.
- Use **2D Nav Goal** only after localization is stable.

If RViz2 has X11 auth problems, on the robot host outside the container:

```bash
xauth extract /tmp/.myxauth $DISPLAY
sudo docker cp /tmp/.myxauth myagv_slam:/tmp/.myxauth
```

Then inside the container:

```bash
export XAUTHORITY=/tmp/.myxauth
rviz2
```

## Optional: named waypoints

1. In RViz2, use **Publish Point** or hover/click known locations on the map.
2. Record the `x, y` coordinates.
3. Put those values into `REAL_WAYPOINTS` in `myagv_lab/phase2_nav/nav_node.py`.
4. Rebuild and run:

```bash
cd /ws
colcon build --packages-select myagv_lab
source /ws/install/setup.bash
export MYAGV_USE_SIM=0
python3 -m myagv_lab.phase2_nav.nav_node --real
```

## Shutdown

When finished:

1. Stop any moving robot command with `Ctrl+C`.
2. Stop Nav2.
3. Stop the base launch.
4. Leave the container with `exit`.

## Common issues

| Problem | Meaning | Fix |
| --- | --- | --- |
| `map does not exist` | AMCL is not active or no initial pose has been sent | Activate `map_server` and `amcl`, then publish initial pose |
| `yaml_filename is not initialized` | Map path was not set before `map_server configure` | Restart Nav2, run `param set` first, then configure |
| Localization jumps by metres | Wrong initial pose | Re-send the initial pose accurately |
| Robot is out of bounds | Initial pose is outside the map | Put the robot on the mapped floor area and re-send pose |
| Goal aborts | Goal is blocked or too close to an obstacle | Pick clearer free space |
| Robot does not move | Base may not be receiving `/cmd_vel` | Test `/cmd_vel` directly |
