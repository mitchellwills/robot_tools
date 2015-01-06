#!/usr/bin/env python3

import os
import sys
import argparse
import yaml
from termcolor import colored
import socket
import netifaces
from netaddr import IPNetwork, IPAddress

class StderrHelpAction(argparse.Action):

    def __init__(self,
                 option_strings,
                 dest=argparse.SUPPRESS,
                 default=argparse.SUPPRESS,
                 help=None):
        super(StderrHelpAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        parser.print_help(file=sys.stderr)
        parser.exit()

def main():
    parser = argparse.ArgumentParser(description='Tool for configuring ROS robot information', prog='robot', add_help=False)
    parser.add_argument('-h', action=StderrHelpAction, default=argparse.SUPPRESS, help='show this help message and exit')
    subparsers = parser.add_subparsers()

    info_parser = subparsers.add_parser('info', help='Display the current configuration', add_help=False)
    info_parser.add_argument('-h', action=StderrHelpAction, default=argparse.SUPPRESS, help='show this help message and exit')
    info_parser.set_defaults(func=info)

    setup_parser = subparsers.add_parser('setup', help='Setup the current robot configuration', add_help=False)
    setup_parser.add_argument('-h', action=StderrHelpAction, default=argparse.SUPPRESS, help='show this help message and exit')
    setup_parser.add_argument('robot')
    setup_parser.add_argument('iface', nargs='?')
    setup_parser.add_argument('-v', action='store_true', dest='verbose', default=False)
    setup_parser.set_defaults(func=setup)

    list_parser = subparsers.add_parser('list', help='List all configured robots', add_help=False)
    list_parser.add_argument('-h', action=StderrHelpAction, default=argparse.SUPPRESS, help='show this help message and exit')
    list_parser.set_defaults(func=robots_list)

    add_parser = subparsers.add_parser('add', help='Add a new robot', add_help=False)
    add_parser.add_argument('-h', action=StderrHelpAction, default=argparse.SUPPRESS, help='show this help message and exit')
    add_parser.add_argument('name', help='The name of the robot')
    add_parser.add_argument('host', metavar='host', help='The host or ip address of the robot')
    add_parser.set_defaults(func=robots_add)

    remove_parser = subparsers.add_parser('remove', help='Remove a robot', add_help=False)
    remove_parser.add_argument('-h', action=StderrHelpAction, default=argparse.SUPPRESS, help='show this help message and exit')
    remove_parser.add_argument('name', help='The name of the robot')
    remove_parser.set_defaults(func=robots_remove)

    if (len(sys.argv) < 2):
        robot()
    else:
        args = parser.parse_args()
        args.func(args)

config_file = os.path.expanduser('~/.robot_tools_config')
def _load_config():
    if os.path.exists(config_file):
        result = yaml.load(open(config_file, 'r'))
        if result is not None:
            return result
    return {}

def _save_config(config):
    return yaml.dump(config, open(config_file, 'w'))

def _get_config_robots(config):
    if 'robots' in config:
        return config['robots']
    else:
        return {}

def robot():
    config = _load_config()
    if 'recent' in config:
        setup(argparse.Namespace(**config['recent']))
    else:
        sys.stderr.write(colored('WARNING:', 'yellow') + ' No recent configuration found \n')

def info(args):
    sys.stderr.write('ROS_MASTER_URI=' + colored(os.environ.get('ROS_MASTER_URI', ''), 'blue', attrs=['bold'])
           + colored(' ['+os.environ.get('ROS_MASTER_URI_CONFIG', '')+']\n', 'cyan'))
    sys.stderr.write('ROS_HOSTNAME=' + colored(os.environ.get('ROS_HOSTNAME', ''), 'blue', attrs=['bold'])
           + colored(' ['+os.environ.get('ROS_HOSTNAME_CONFIG', '')+']\n', 'cyan'))


def setup(args):
    config = _load_config()
    robots = _get_config_robots(config)

    if args.robot in robots:
        if args.verbose:
            sys.stderr.write('Loaded robot: '+args.robot+'\n')
        robot_config = robots[args.robot]
        host = robot_config['host']
    else:
        sys.stderr.write(colored('WARNING:', 'yellow') + ' Treating '+args.robot+' as hostname or IP\n')
        host = args.robot

    try:
        master_addr = IPAddress(socket.gethostbyname(host))
        if args.verbose:
            sys.stderr.write('Resolved master host to '+str(master_addr)+'\n')
    except socket.gaierror:
        sys.stderr.write(colored('ERROR:', 'red') + ' Could not resolve robot host to ip address: '+host+'\n')
        return

    local_addr = None
    local_iface_config = None
    if args.iface:
        if args.verbose:
            sys.stderr.write('Using address on '+args.iface+'\n')
        if args.iface in netifaces.interfaces():
            addresses = netifaces.ifaddresses(args.iface)
            if netifaces.AF_INET in addresses and addresses[netifaces.AF_INET]:
                ipv4_addresses = addresses[netifaces.AF_INET]
                address = ipv4_addresses[0]
                local_addr = address['addr']
                local_iface_config = args.iface
            else:
                sys.stderr.write(colored('ERROR:', 'red') + ' No IPv4 address for '+args.iface+'\n')
                return
        else:
            sys.stderr.write(colored('ERROR:', 'red') + ' '+args.iface+' is not a valid interface\n')
            sys.stderr.write('NOTE: Interfaces are: '+str(netifaces.interfaces())+'\n')
            return
    else:
        for iface in netifaces.interfaces():
            addresses = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addresses:
                ipv4_addresses = addresses[netifaces.AF_INET]
                for address in ipv4_addresses:
                    network = IPNetwork(address['addr']+'/'+address['netmask'])
                    if master_addr in network:
                        if args.verbose:
                            sys.stderr.write('Found robot on '+iface+' ('+str(network)+')\n')
                        local_addr = address['addr']
                        local_iface_config = iface+' (auto)'

    if local_addr is not None:
        if args.verbose:
            sys.stderr.write('Found local address: '+str(local_addr)+'\n')

        master_uri = 'http://'+host+':11311/'
        print('export ROS_MASTER_URI="'+master_uri+'"\n')
        print('export ROS_HOSTNAME="'+local_addr+'"\n')
        print('export ROS_MASTER_URI_CONFIG="'+args.robot+'"\n')
        print('export ROS_HOSTNAME_CONFIG="'+local_iface_config+'"\n')

        sys.stderr.write('ROS_MASTER_URI=' + colored(master_uri, 'blue', attrs=['bold'])
                         + colored(' ['+args.robot+']\n', 'cyan'))
        sys.stderr.write('ROS_HOSTNAME=' + colored(local_addr, 'blue', attrs=['bold'])
                         + colored(' ['+local_iface_config+']\n', 'cyan'))

        config['recent'] = {'robot': args.robot, 'iface': args.iface, 'verbose': args.verbose}
        _save_config(config)

    else:
        sys.stderr.write(colored('ERROR:', 'red') + ' No local address found for master: '+str(master_addr)+'\n')


def robots_list(args):
    config = _load_config()
    robots = _get_config_robots(config)

    sys.stderr.write('Robots:\n')
    for robot in robots:
        robot_config = robots[robot]
        sys.stderr.write('\t'+robot+': '+robot_config['host']+'\n')

def robots_add(args):
    config = _load_config()
    robots = _get_config_robots(config)

    if args.name in robots:
        sys.stderr.write(args.name + ' is already a defined robot\n')
    else:
        robots[args.name] = {'host': args.host}
        config['robots'] = robots
        _save_config(config)

def robots_remove(args):
    config = _load_config()
    robots = _get_config_robots(config)

    if args.name in robots:
        del robots[args.name]
    else:
        sys.stderr.write(args.name + ' is not a defined robot\n')
    config['robots'] = robots
    _save_config(config)



if __name__ == "__main__":
    main()
