#!/usr/bin/python

def find_sources():
    import os
    import sys
    base_path = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(base_path, "launch_control")):
        sys.path.append(base_path)


find_sources()

if __name__ == '__main__':
    try:
        from launch_control.commands.dispatcher import main
    except ImportError:
        print "Unable to import launch_control.commands.dispatcher"
        print "Your installation is probably faulty"
        raise
    else:
        main()
