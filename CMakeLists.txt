cmake_minimum_required(VERSION 2.8.3)
project(robot_tools)

find_package(catkin REQUIRED)


catkin_python_setup()

catkin_package()

catkin_add_env_hooks(15.robot_tools SHELLS bash)
