function robot() {
    local out=`robot_tools.py "$@@"`
    eval "$out"
}
# Load the most recent configuration and display it
robot
